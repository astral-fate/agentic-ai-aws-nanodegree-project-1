# Submission — rubric to evidence

Every rubric line, where it is satisfied, and what proves it.

> **One note on the rubric's wording.** It was written when this project was
> built on **Bedrock Flows**, and still asks for a "flow diagram", "Condition
> node expressions", "Output nodes" and a "FAQ Prompt node template". The
> course has since moved to the **AgentCore managed harness**, and the Project
> Overview is explicit about what replaced them:
>
> > *"The centerpiece of this project is prompt engineering: all of the
> > routing, information gathering, and grounding behavior lives in a single
> > system prompt that you design. … There are no condition nodes or separate
> > classifiers."*
>
> So there is no flow canvas to screenshot. Each affected row below names the
> AgentCore artefact that plays the same role. Nothing is skipped — the
> requirement is met, the evidence just lives in a file instead of a diagram.

**Status key:** ✅ done and verified · ⏳ awaiting re-run · 📸 needs a screenshot from you

---

## 1. Implement Classification and Routing

| Requirement | Status | Where |
|---|---|---|
| Classifies messages into distinct categories | ✅ | [`system_prompt.txt`](project/starter/system_prompt.txt) — `STEP 1 - CLASSIFY`, three categories with signals and worked near-miss examples |
| Classifier output is consistent and unambiguous, and can drive routing | ✅ | Classification is an explicit silent first step; the model must pick exactly one before acting. Greedy decoding (temperature 0, topK 1) is pinned in `create_harness.py` |
| Messages routed to distinct paths by category | ✅ | `STEP 2 - ACT ON THE CATEGORY YOU CHOSE` — three separate behaviour blocks |
| Distinct paths, each ending at a separate Output node | ✅ | *Flows-era wording.* The three terminal behaviours are: a `create_bug_report` tool call plus ticket ID, an FAQ-grounded answer, and the `1-800-555-0199` hand-off. They are mutually exclusive and independently tested |

**Evidence**

- *Flow diagram* → [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) has the
  system diagram; the routing lives in the prompt, not a canvas.
- *Classifier prompt configuration* → `system_prompt.txt`, `STEP 1`.
- *Condition node expressions* → no such node exists. The equivalent is the
  category definitions plus the near-miss table:

  ```
  "Why was my payment declined?"        -> PLATFORM_QUESTION (FAQ item 20)
  "The payment page shows a 500 error"  -> BUG_REPORT
  ```

- Live routing output: run step **09 Route spot checks**.
- Design rationale: [`docs/PROMPT_DESIGN.md`](docs/PROMPT_DESIGN.md).

---

## 2. Implement the Bug Report Path

| Requirement | Status | Where |
|---|---|---|
| Path defined in the system prompt, no separate agent resource | ✅ | `system_prompt.txt`, `--- BUG_REPORT ---` |
| Harness invokes the Lambda tool through the AgentCore Gateway to persist the ticket | ✅ | Verified live: gateway `bug-report-tool-stack-gateway-stuq8vnpha`, target `bugreports`, tool `bugreports___create_bug_report` |
| Collects description, steps to reproduce and environment **before** calling the tool | ⏳ | **Failed in run 1**, prompt fixed, needs re-run to confirm — see below |
| A record is created in `bug-report-tool-stack-bug-reports` | ✅ | 11 items after run 1; `evidence/dynamodb_bug_reports.json` |

**Evidence**

- `system_prompt.txt` showing the route and its collection rules — the
  `THE GATE` block.
- Transcript with follow-up questions and the
  `[tool call] bugreports___create_bug_report` line →
  `evidence/bug_report_transcript.txt`, produced by
  [`scripted_bug_report.py`](project/starter/scripted_bug_report.py).
- 📸 DynamoDB console → `bug-report-tool-stack-bug-reports` → **Explore items**.

> ### ⚠️ The one open item
>
> In run 1 Nova called `create_bug_report` on **turn 1** with only a
> description, inventing the steps and environment, then filed a duplicate on
> turn 2. That fails this row, and the run-1 transcript shows the failure.
>
> Fixed by replacing a negative constraint with one that has a checkable
> trigger — *"Your FIRST reply to a bug report is ALWAYS a question, never a
> tool call"* — plus an explicit ban on inventing values and an explanation of
> why a second call is harmful.
>
> **Re-run before submitting.** Step 08 must print `ALL 7 CHECKS PASSED`, and
> the transcript must show the follow-up questions. Full analysis in
> [`docs/EVALUATION.md`](docs/EVALUATION.md).

---

## 3. Implement Platform Question and Other Request Paths

| Requirement | Status | Where |
|---|---|---|
| Relevant answer when the FAQ covers the question | ✅ | Run 1: *"How long do I have to return something?"* → 30 days, unused, original packaging, defective exception |
| Directs to the support phone number when the FAQ does not cover it | ✅ | Run 1: *"Do you price match?"* → declined to invent a policy, gave `1-800-555-0199` |
| A separate path for other requests, directing to the phone number | ⏳ | Run 1: the brownie-recipe case skipped the hand-off. Prompt fixed (OTHER is now stated as the default); needs re-run |

**Evidence**

- *FAQ Prompt node template showing embedded FAQ content* → the AgentCore
  equivalent is `{{FAQ}}` in `system_prompt.txt`, substituted by
  `create_harness.py` at upload time. The run writes
  `evidence/rendered_system_prompt.txt` — the exact 14,071-character prompt
  the harness received, FAQ included.
- Responses for a covered question, an uncovered question and an
  other-request message → run step **09**.
- [`online_shop_faq.md`](project/starter/online_shop_faq.md), extended with a
  gift-card section (stand-out item — see below).

---

## 4. Implement the Testing and Evaluation

| Requirement | Status | Where |
|---|---|---|
| `flow-tests.json` has ≥1 test per path | ✅ | [`flow-tests.json`](project/starter/flow-tests.json) — 21 cases: 6 bug, 9 platform, 6 hand-off. Also shipped as `harness-tests.json`, the name the current instructions use; a test asserts the two never diverge |
| `generate-eval-dataset.py` produces a JSONL file | ✅ | Run 1: 21 records, 21 harness calls succeeded, **0 `[HARNESS_ERROR]`** |
| JSONL uploaded to S3 and an evaluation job created | ✅ | Job `support-chatbot-eval-1787431707`, status **Completed**, bucket `udacity-agentic-engineer-c1-eval-212626318772` |
| Correctness score close to 1 | ⏳ | Not yet measured — the parser looked for the wrong key. Fixed; run 2 prints the mean and distribution |

**Evidence**

- `flow-tests.json` and `output_eval_dataset.jsonl` → both in
  `evidence.tar.gz`.
- 📸 Bedrock console → **Evaluations** → job → results page.
- Written observations → [`docs/EVALUATION.md`](docs/EVALUATION.md), with the
  run-1 transcript, four findings, and the change table.

---

## Stand-out suggestions

| Suggestion | Status | Where |
|---|---|---|
| **Guardrail blocking harmful content and prompt injection before any model processes the message** | ✅ | [`setup_guardrail.py`](project/starter/setup_guardrail.py), [`guardrail.py`](project/starter/guardrail.py), [`chat_guarded.py`](project/starter/chat_guarded.py). Exercised by run step **10** |
| **Edge-case prompts: ambiguous, very short, injection** | ✅ | `t03` two-word *"site broken"*; `t18`/`t21` designed near misses; `t19`/`t20` injection |
| **Replace the embedded FAQ with a Bedrock Knowledge Base** | ❌ | Not done — the course notes place RAG with Knowledge Bases outside its scope |
| **Structured output so the classifier only produces valid values** | ➖ | No classifier node exists in AgentCore. The nearest equivalent is enforced: the tool's JSON Schema constrains the tool call, and the Lambda rejects blank required fields |

### On the guardrail

Worth being precise, because it is the strongest stand-out item here.

The AgentCore harness API has **no guardrail field** — `CreateHarness`,
`UpdateHarness` and `InvokeHarness` accept `model`, `tools`, `systemPrompt`,
`memory` and so on, with nowhere to attach a guardrail ARN. So the guardrail
is applied by the caller with `bedrock-runtime:ApplyGuardrail` *ahead of*
`invoke_harness`. That ordering is exactly what the suggestion asks for: a
blocked message never reaches Nova Pro, spends no tokens, and cannot trigger a
tool.

It uses the `PROMPT_ATTACK` filter at `HIGH` plus two denied topics —
`RefundAuthorization` and `SystemInstructionDisclosure` — which are the two
things injection attempts here actually aim for. It **fails open**: a
guardrail outage degrades protection rather than taking the chatbot down,
since the system prompt's own defences still apply.

This is defence in depth. The prompt's injection block persuades the model to
refuse — which means the model has already read the attack. The guardrail
stops it earlier.

### Also beyond the rubric

- **115 offline tests** (`python -m pytest`, ~4s, no AWS) covering the real
  Lambda, the streaming parsers, the dataset writer, both CloudFormation
  templates, and the prompt's structural invariants.
- **One-command reproduction** —
  [`cloudshell/PASTE-THIS.txt`](cloudshell/PASTE-THIS.txt) runs the entire
  project end to end in AWS CloudShell, resumable, with an integrity check.
- **`scripted_bug_report.py`** — drives a real multi-turn conversation and
  verifies the stored DynamoDB item field-by-field against what the customer
  said. This is what caught the run-1 failure.
- **Evidence bundling** — the run collects every artefact into
  `evidence.tar.gz`.

---

## Before you submit

1. **Re-run** — upload the current `run-all.sh` and `bash run-all.sh`.
   The harness updates in place; no teardown needed.
2. **Confirm step 08 prints `ALL 7 CHECKS PASSED`.** This is the one rubric
   row still failing. Do not submit until it does.
3. **Note the correctness score** printed at step 12 and paste it into
   `docs/EVALUATION.md` → Run 2.
4. **Download `evidence.tar.gz`** (CloudShell → Actions → Download file).
5. **Take three screenshots:** the Bedrock Evaluations results page, the
   DynamoDB table with items, and the Lambda console test result.
6. **Check the brownie case** returns `1-800-555-0199` at step 09.
7. Switch off root credentials — run 1 used
   `arn:aws:iam::212626318772:root`. See [`docs/SECURITY.md`](docs/SECURITY.md).
8. **Tear down** once the screenshots are captured; the commands are printed
   at the end of the run.
