# Architecture

## The shape of the system

```
                     ┌──────────────┐
   customer ────────▶│   chat.py    │  one conversation per run
                     └──────┬───────┘  (one runtimeSessionId)
                            │ InvokeHarness
                            ▼
        ┌───────────────────────────────────────────┐
        │      AgentCore managed harness            │
        │      "support_chatbot"                    │
        │                                           │
        │   • runs the agent loop server-side       │
        │   • keeps session state across turns      │
        │   • model pinned: us.amazon.nova-pro-v1:0 │
        │   • system prompt = system_prompt.txt     │
        │     with {{FAQ}} → online_shop_faq.md     │
        └───────────┬───────────────────┬───────────┘
                    │                   │
         model call │                   │ tool call
                    ▼                   ▼
        ┌───────────────────┐   ┌───────────────────────┐
        │  Bedrock          │   │  AgentCore Gateway    │
        │  Nova Pro         │   │  target: bugreports   │
        │  temp 0, topK 1   │   │  protocol: MCP        │
        └───────────────────┘   │  auth: AWS_IAM        │
                                └───────────┬───────────┘
                                            │ Invoke
                                            ▼
                                ┌───────────────────────┐
                                │  Lambda               │
                                │  ...create-bug-report │
                                └───────────┬───────────┘
                                            │ PutItem
                                            ▼
                                ┌───────────────────────┐
                                │  DynamoDB             │
                                │  ...-bug-reports      │
                                │  key: ticketId        │
                                └───────────────────────┘
```

The model sees the tool as **`bugreports___create_bug_report`** — the gateway
target name, three underscores, then the tool name. That prefix is why target
names may only contain letters, digits and underscores: a dash there breaks
Nova tool calling with *"Model produced invalid sequence as part of ToolUse"*.

## Where the intelligence lives

All of it is in `system_prompt.txt`. There is no classifier node, no router
Lambda, no condition expression. The harness supplies the loop — model calls,
session memory, tool execution — and the prompt supplies the behaviour.

That is the point of the project: **routing is a prompt engineering problem
here**, and the quality of the category definitions is what determines whether
messages land in the right place.

## Statefulness

The harness keeps conversation state keyed by `runtimeSessionId`. That is what
makes multi-turn bug collection possible — the assistant can ask for one
missing field at a time and the earlier answers are still there.

Two consequences worth knowing:

- **`chat.py` = one conversation.** Each run generates a fresh session id, so
  restarting the script starts over. Session ids must be at least 33
  characters (the scripts use a UUID plus a suffix).
- **Every evaluation case is independent.** `generate-eval-dataset.py` makes a
  new session per test case, so cases cannot contaminate each other. It also
  means a test prompt cannot rely on earlier turns — which is why the
  bug-report cases in `harness-tests.json` describe the *start* of collection
  rather than a finished ticket.

## The tool contract

The gateway passes the tool arguments **directly as the Lambda event** — a
plain JSON object, no envelope:

```json
{
  "description": "The checkout page crashes when I click the Pay button",
  "stepsToReproduce": "1. Add an item to the cart. 2. Go to checkout. 3. Click Pay.",
  "environment": "Chrome 120 on macOS Sonoma"
}
```

(Bedrock Agents Classic wrapped these in a `messageVersion`/`parameters`
structure. The gateway does not.)

The tool name arrives separately, via
`context.client_context.custom["bedrockAgentCoreToolName"]`.

Whatever the handler returns goes back to the model as the tool result — so
`{"ticketId": "...", "status": "OPEN"}` on success, and on failure a
`{"error": "missing required field(s): ..."}` that tells the model to go back
and ask the customer rather than filing an incomplete ticket. That error path
matters: Nova will occasionally try to satisfy a required parameter with an
empty string, and the Lambda is the last line of defence against a junk
ticket.

## Resources the stacks create

**`bug-report-tool-stack`** (from `cloudformation-tool.yaml`):

| Resource | Name | Purpose |
|---|---|---|
| DynamoDB table | `bug-report-tool-stack-bug-reports` | One item per ticket, keyed by `ticketId` |
| Lambda | `bug-report-tool-stack-create-bug-report` | The tool implementation |
| IAM role | `bug-report-tool-stack-lambda-role` | Logs + `PutItem` on the table |
| IAM role | `bug-report-tool-stack-gateway-role` | Assumed by the gateway to invoke the Lambda |
| IAM role | `bug-report-tool-stack-harness-role` | Assumed by the harness to call Bedrock and the gateway |

**`bug-report-testing-stack`** (from `cloudformation-testing.yaml`):

| Resource | Name | Purpose |
|---|---|---|
| S3 bucket | `udacity-agentic-engineer-c1-eval-<ACCOUNT_ID>` | Eval dataset in, results out |
| IAM role | Bedrock Evaluations role | Assumed by the evaluation job |

Created outside CloudFormation, by `setup_gateway.py` and `create_harness.py`:
the **gateway**, its **target**, and the **harness** — all recorded in
`agentcore_config.json`, which is git-ignored because it contains account
IDs and resource ARNs. `cleanup_agentcore.py` deletes them in the right order
(harness → target → gateway).

## Evaluation path

```
harness-tests.json
      │ generate-eval-dataset.py  (one fresh session per case)
      ▼
output_eval_dataset.jsonl
      │ run_evaluation.py  →  S3 upload  →  CreateEvaluationJob
      ▼
Bedrock Evaluations  (LLM-as-a-judge, bring-your-own-inference)
      ▼
s3://…/results/   +   console scores
```

Bedrock Evaluations cannot invoke the harness itself, so we run the harness
first, store its answers, and hand the file over. **BYOI** — bring your own
inference — is the mode for that: the judge only scores, it never generates.

The one field that silently ruins a run: `modelIdentifier` in every JSONL
record must equal `inferenceSourceIdentifier` in the job config. If they
differ, Bedrock matches nothing and scores nothing. `run_evaluation.py`
derives both from the same argument and refuses to upload a file where they
disagree.
