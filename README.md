# Agentic AI — AWS Nanodegree, Project 1

**Customer Support Chatbot with Amazon Bedrock AgentCore**

A customer support chatbot for a fictional online shop, built on the Amazon
Bedrock **AgentCore managed harness**. Every incoming message is routed to one
of three behaviours — and all of the routing lives in a single system prompt,
not in condition nodes or a separate classifier.

| Route | Behaviour |
|---|---|
| **Bug report** | Collects the description, the steps to reproduce, and the customer's environment across the conversation, then files a ticket via the `create_bug_report` tool (Lambda → DynamoDB) and relays the ticket ID |
| **Platform question** | Answers from the embedded FAQ **only** — orders, shipping, returns, refunds, payments, products, accounts, privacy |
| **Anything else** | Politely hands off to the human support line, `1-800-555-0199` |

---

## Status

| | |
|---|---|
| Offline test suite | **83 tests, all passing** — `python -m pytest` |
| System prompt | Written, hardened against prompt injection |
| Test suite for evaluation | 21 cases across all three routes + edge cases |
| AWS deployment | **Not yet run** — needs credentials, see [below](#before-you-can-deploy) |
| Bedrock Evaluations run | **Not yet run** — [`docs/EVALUATION.md`](docs/EVALUATION.md) is ready to record it |

The offline suite exercises the real Lambda, the real streaming parsers, the
real dataset writer and the real templates. It does **not** exercise Nova
Pro's judgement — only a live Bedrock Evaluations run can score the routing
quality. See [What the tests do and do not prove](#what-the-tests-do-and-do-not-prove).

---

## Before you can deploy

Two things are missing on this machine, and neither is something the project
can work around:

1. **The AWS CLI is not installed.** `aws --version` → not found.
   Install it from
   <https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html>,
   or run the CloudFormation steps from the Udacity workspace instead.

2. **No credentials for this project's AWS account.** `.env` has the slots
   ready but empty. The `saudispace` keys that are also in `.env` **cannot**
   run this project — their IAM policy grants only
   `s3:PutObject/GetObject/DeleteObject` on `arn:aws:s3:::saudispace/*`, in
   `eu-north-1`. This project needs CloudFormation, Lambda, DynamoDB, IAM,
   Bedrock and Bedrock AgentCore in `us-east-1`.

> ⚠️ **Rotate the `saudispace` keys.** They were pasted in plaintext into a
> chat transcript, so treat them as compromised. See
> [`docs/SECURITY.md`](docs/SECURITY.md).

Everything else — the prompt, the tests, the templates, the scripts — is
finished and verified as far as it can be without an account.

---

## Quick start

```bash
git clone <this repo>
cd agentic-ai-aws-nanodegree-project-1

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

cp .env.example .env              # then fill in your AWS keys

python -m pytest                  # 83 offline tests, no AWS needed
```

Loading `.env` into your shell:

```bash
set -a && source .env && set +a                      # bash / git-bash
```
```powershell
Get-Content .env | ForEach-Object {                  # PowerShell
  if ($_ -match '^\s*([^#=]+)=(.*)$') {
    [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process') } }
```

## Deploying to AWS

Every command runs from `project/starter/`. The full walkthrough, with
troubleshooting, is in [`docs/RUNBOOK.md`](docs/RUNBOOK.md).

There is also a `Makefile` with shortcuts (`make test`, `make deploy-all`,
`make evaluate`, `make clean-aws`) — but **`make` is not installed on this
machine**, so the commands below are the ones to use. `make help` lists the
targets wherever `make` is available.

```bash
cd project/starter

# 1. Tool stack: DynamoDB table + Lambda + IAM roles
aws cloudformation deploy --template-file cloudformation-tool.yaml \
  --stack-name bug-report-tool-stack --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1

# 2. Gateway: exposes the Lambda as the create_bug_report tool
python setup_gateway.py            # writes agentcore_config.json

# 3. Harness: uploads system_prompt.txt with {{FAQ}} substituted
python create_harness.py           # first run ~2-3 minutes

# 4. Try it
python chat.py

# 5. Evaluate
aws cloudformation deploy --template-file cloudformation-testing.yaml \
  --stack-name bug-report-testing-stack --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
python generate-eval-dataset.py --tests-json harness-tests.json
python run_evaluation.py --wait

# 6. Tear down
python cleanup_agentcore.py
```

Iterating on the prompt is just: edit `system_prompt.txt`, re-run
`create_harness.py`, start a fresh `chat.py`. Nothing is redeployed.

---

## What's in here

```
project/starter/               every command runs from this folder
  system_prompt.txt            ★ the main deliverable — all routing lives here
  harness-tests.json           ★ 21 evaluation cases across the three routes
  online_shop_faq.md             the shop's FAQ, extended with gift-card entries
  run_evaluation.py            ★ uploads the dataset and starts the eval job
  cloudformation-tool.yaml       DynamoDB + Lambda + 3 IAM roles
  cloudformation-testing.yaml    S3 bucket + Bedrock Evaluations role
  create_bug_report.py           the Lambda behind the tool
  setup_gateway.py               creates the gateway, registers the tool
  create_harness.py              creates/updates the harness from the prompt
  chat.py                        terminal client, one conversation per run
  generate-eval-dataset.py       runs the suite, writes the JSONL
  cleanup_agentcore.py           deletes harness, target, gateway

tests/                         ★ offline end-to-end suite (no AWS required)
  fake_agentcore.py              stand-in for the AgentCore runtime
  test_lambda_handler.py         the real Lambda, faked table
  test_system_prompt.py          structural checks on the deliverable
  test_harness_tests_suite.py    route coverage in the eval suite
  test_cloudformation.py         template structure and output names
  test_end_to_end_offline.py     full pipeline, multi-turn bug reports
  test_run_evaluation.py         the eval dataset pre-flight validator

docs/
  ARCHITECTURE.md                how the pieces fit, with a diagram
  RUNBOOK.md                     deploy, verify, iterate, tear down
  PROMPT_DESIGN.md               why the prompt is shaped the way it is
  EVALUATION.md                  the evaluation method + results template
  SECURITY.md                    credential handling and the rotation notice
```

★ = written for this project. Everything else is the Udacity starter,
unchanged, so the graded files stay byte-identical to what the course ships.

---

## What the tests do and do not prove

`python -m pytest` runs 83 tests with no AWS account and no network. The
pipeline they exercise is the real one everywhere it can be:

```
chat.py / generate-eval-dataset.py     ← real starter code
    └─ invoke_harness                  ← faked (tests/fake_agentcore.py)
        └─ tool call via gateway       ← faked
            └─ lambda_handler          ← REAL code from create_bug_report.py
                └─ DynamoDB put_item   ← faked in-memory table
    └─ streamed event parsing          ← real
    └─ output_eval_dataset.jsonl       ← real writer, schema asserted
```

**Proven offline:** the Lambda's validation and DynamoDB writes; that a blank
required field is rejected instead of filed; that tickets get unique IDs; that
the streaming parser finds tool calls and text; that a bug report is collected
across several turns and files exactly one ticket; that sessions stay isolated;
that the JSONL matches the Bedrock Evaluations BYOI schema; that the CFN
outputs `setup_gateway.py` reads by name actually exist; that the Lambda code
embedded in the template hasn't drifted from the standalone file.

**Not proven offline:** whether Nova Pro actually routes messages correctly.
The routing in the offline suite is done by a keyword matcher
(`ScriptedModel`) that mirrors the prompt's rules — it makes the tests
deterministic, but a green run means *"the wiring is correct"*, not *"the
model behaves"*. That question is what the Bedrock Evaluations run answers,
and [`docs/EVALUATION.md`](docs/EVALUATION.md) is where its results go.

---

## Design notes

The interesting decisions are written up in
[`docs/PROMPT_DESIGN.md`](docs/PROMPT_DESIGN.md). The short version:

- **Classify first, then act.** The prompt makes categorisation an explicit
  first step with crisp definitions, because vague categories produce vague
  routing.
- **Bug reports are sticky.** Once collection starts it continues until the
  ticket is filed, so a bare `"Chrome"` reads as an answer rather than a new
  request.
- **The near-miss cases are called out by name.** *"Why was my payment
  declined?"* is an FAQ question; *"the payment page shows a 500 error"* is a
  bug. Those two lines do more for routing accuracy than any amount of
  general instruction.
- **The FAQ is fenced as data.** Everything after `--- FAQ document ---` is
  labelled untrusted reference material, so an injection hidden in the FAQ
  cannot take over.
- **One question per message**, per the project tips — it measurably beats
  asking for all three fields at once.

---

## Cost and cleanup

DynamoDB is on-demand, the Lambda is free-tier-sized, and the gateway and
harness cost nothing at rest. The real spend is Nova Pro tokens: the whole
FAQ is re-sent on every turn (~7 KB), and a 21-case evaluation run is roughly
21 harness invocations plus 21 judge calls.

Tear everything down with `make clean-aws`, or follow Step 6 above. Empty the
S3 bucket **before** deleting the testing stack — CloudFormation cannot delete
a non-empty bucket and the stack ends up in `DELETE_FAILED`.
