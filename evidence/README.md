# Evidence — every rubric item, shown inline

Nothing here needs opening a folder. Each rubric Evidence line is answered
below with the image or file right underneath it.

**Current run: [`run-02/`](run-02/)** — Correctness **1.000** over 21 records,
`ALL 8 CHECKS PASSED` on the bug report, all five route checks green.
`run-01/` is the earlier run (0.952) that
[`../docs/EVALUATION.md`](../docs/EVALUATION.md) compares against.

> **Note for the reviewer.** This project is built on the **AgentCore managed
> harness**, which the course moved to — not Bedrock Flows. The Project
> Overview states it directly: *"all of the routing, information gathering,
> and grounding behavior lives in a single system prompt that you design …
> There are no condition nodes or separate classifiers."*
>
> So there is no console canvas to screenshot. Every requirement is still met
> and shown below — the flow, the classifier, the routing conditions and the
> embedded FAQ all exist, in `system_prompt.txt` and in the live run output
> rather than on a diagram surface. Images 06–10 render that real content;
> images 01–05 are genuine AWS console screenshots.

## Every image, with its path

| Image | Rubric item | Path |
|---|---|---|
| [**Full flow diagram**](run-02/screenshots/06-flow-diagram.png) | §1 · the whole flow, three distinct outputs | [`evidence/run-02/screenshots/06-flow-diagram.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/06-flow-diagram.png) |
| [**Classifier prompt**](run-02/screenshots/07-classifier-prompt.png) | §1 · `STEP 1 - CLASSIFY`, verbatim | [`evidence/run-02/screenshots/07-classifier-prompt.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/07-classifier-prompt.png) |
| [**Condition expressions**](run-02/screenshots/08-condition-expressions.png) | §1 · routing rules + near-miss pairs | [`evidence/run-02/screenshots/08-condition-expressions.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/08-condition-expressions.png) |
| [**FAQ embedded in the prompt**](run-02/screenshots/09-faq-embedded-in-prompt.png) | §3 · `{{FAQ}}` before and after substitution | [`evidence/run-02/screenshots/09-faq-embedded-in-prompt.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/09-faq-embedded-in-prompt.png) |
| [**Route responses**](run-02/screenshots/10-faq-and-handoff-responses.png) | §3 · covered · uncovered · other-request | [`evidence/run-02/screenshots/10-faq-and-handoff-responses.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/10-faq-and-handoff-responses.png) |
| [**Evaluation report — Correctness 1.00**](run-02/screenshots/01b-evaluation-job-results.png) | §4 · the score, close to 1 | [`evidence/run-02/screenshots/01b-evaluation-job-results.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/01b-evaluation-job-results.png) |
| [Bedrock Evaluations list](run-02/screenshots/01-bedrock-evaluations.png) | §4 · the job was created and Completed | [`evidence/run-02/screenshots/01-bedrock-evaluations.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/01-bedrock-evaluations.png) |
| [DynamoDB bug reports](run-02/screenshots/02-dynamodb-bug-reports.png) | §2 · tickets the chatbot filed | [`evidence/run-02/screenshots/02-dynamodb-bug-reports.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/02-dynamodb-bug-reports.png) |
| [Lambda `create_bug_report`](run-02/screenshots/03-lambda-create-bug-report.png) | the tool implementation | [`evidence/run-02/screenshots/03-lambda-create-bug-report.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/03-lambda-create-bug-report.png) |
| [CloudWatch logs](run-02/screenshots/04-lambda-cloudwatch-logs.png) | real invocations through the gateway | [`evidence/run-02/screenshots/04-lambda-cloudwatch-logs.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/04-lambda-cloudwatch-logs.png) |
| [CloudFormation stacks](run-02/screenshots/05-cloudformation-stacks.png) | deployed infrastructure | [`evidence/run-02/screenshots/05-cloudformation-stacks.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/05-cloudformation-stacks.png) |

All eleven are embedded further down, each under the rubric line it
answers. Click any image to open it full size.

---

## 1. Implement Classification and Routing

### Screenshot of the full flow diagram

One classification step, three mutually exclusive paths, each terminating at
its own distinct output.

[![Full flow diagram](run-02/screenshots/06-flow-diagram.png)](run-02/screenshots/06-flow-diagram.png)

<sub>🔍 [Open full size](run-02/screenshots/06-flow-diagram.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/06-flow-diagram.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/06-flow-diagram.png)</sub>

### Screenshot of the classifier prompt configuration

The `STEP 1 - CLASSIFY` block, quoted verbatim from `system_prompt.txt`. It
runs before any reply is written and must select exactly one category.

[![Classifier prompt](run-02/screenshots/07-classifier-prompt.png)](run-02/screenshots/07-classifier-prompt.png)

<sub>🔍 [Open full size](run-02/screenshots/07-classifier-prompt.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/07-classifier-prompt.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/07-classifier-prompt.png)</sub>

### Screenshot of the Condition node expressions

The routing rules. The worked near-miss pairs are the load-bearing part —
both sides mention something going wrong, and the rule is whether the FAQ has
an answer or the software is genuinely broken.

[![Condition expressions](run-02/screenshots/08-condition-expressions.png)](run-02/screenshots/08-condition-expressions.png)

<sub>🔍 [Open full size](run-02/screenshots/08-condition-expressions.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/08-condition-expressions.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/08-condition-expressions.png)</sub>

---

## 2. Implement the Bug Report Path

### The submitted `system_prompt.txt` showing the bug-report route

[`run-02/system_prompt.txt`](run-02/system_prompt.txt) — the
`--- BUG_REPORT ---` section, including `THE GATE`. Also visible in image 08
above.

### Transcript showing the follow-up questions and the tool-call line

From [`run-02/bug_report_transcript.txt`](run-02/bug_report_transcript.txt):

```
you> Your checkout page crashes every single time I click the Pay button.
bot> I'm sorry to hear you're experiencing this issue. Could you please
     describe the steps you took that led to the crash?

you> I add a pair of headphones to the cart, go to checkout, fill in my card
     details and then click Pay. The page goes white straight away.
bot> Thank you for providing the steps. To help resolve this, could you
     please let me know which browser and device you are using?

you> I'm using Chrome 120 on macOS Sonoma, on a MacBook Air.
[tool call] bugreports___create_bug_report
bot> The bug has been successfully reported with ticket ID
     2dd5cc3c-d1c6-490c-ba07-627052aed0cb.
```

One question per turn, all three fields collected from the customer, then a
single tool call and the ticket ID relayed.

### DynamoDB table showing an item created by the chatbot

[![DynamoDB bug reports](run-02/screenshots/02-dynamodb-bug-reports.png)](run-02/screenshots/02-dynamodb-bug-reports.png)

<sub>🔍 [Open full size](run-02/screenshots/02-dynamodb-bug-reports.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/02-dynamodb-bug-reports.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/02-dynamodb-bug-reports.png)</sub>

The stored item for the conversation above:

```
description      : Checkout page crashes when clicking the Pay button.
stepsToReproduce : Add a pair of headphones to the cart, go to checkout,
                   fill in card details, and click Pay. The page goes white
                   immediately.
environment      : Chrome 120 on macOS Sonoma, MacBook Air.
status           : OPEN
```

---

## 3. Implement Platform Question and Other Request Paths

### FAQ Prompt node template showing embedded FAQ content

`create_harness.py` replaces `{{FAQ}}` with `online_shop_faq.md` at upload
time, so the model sees the whole FAQ at inference.

[![FAQ embedded in the prompt](run-02/screenshots/09-faq-embedded-in-prompt.png)](run-02/screenshots/09-faq-embedded-in-prompt.png)

<sub>🔍 [Open full size](run-02/screenshots/09-faq-embedded-in-prompt.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/09-faq-embedded-in-prompt.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/09-faq-embedded-in-prompt.png)</sub>

Full substituted prompt:
[`run-02/rendered_system_prompt.txt`](run-02/rendered_system_prompt.txt)
(17,706 characters).

### Responses for a covered question, an uncovered question and an other-request message

The chatbot's actual replies, recorded during the evaluation run. All three
scored 1.0.

[![Route responses](run-02/screenshots/10-faq-and-handoff-responses.png)](run-02/screenshots/10-faq-and-handoff-responses.png)

<sub>🔍 [Open full size](run-02/screenshots/10-faq-and-handoff-responses.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/10-faq-and-handoff-responses.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/10-faq-and-handoff-responses.png)</sub>

---

## 4. Implement the Testing and Evaluation

### `flow-tests.json` with at least one entry per path

[`run-02/flow-tests.json`](run-02/flow-tests.json) — 21 cases: **6 bug
report, 9 platform question, 6 hand-off**, including edge cases (a two-word
message, two designed near misses, two prompt-injection attempts). Shipped
also as `harness-tests.json`, the name the current instructions use.

### JSONL output file

[`run-02/output_eval_dataset.jsonl`](run-02/output_eval_dataset.jsonl) — 21
records, no harness errors.

### Bedrock Evaluation job results page, and the correctness score

**Correctness 1.00** — average 1.000 across all 21 prompts.

[![Bedrock evaluation report](run-02/screenshots/01b-evaluation-job-results.png)](run-02/screenshots/01b-evaluation-job-results.png)

<sub>🔍 [Open full size](run-02/screenshots/01b-evaluation-job-results.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/01b-evaluation-job-results.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/01b-evaluation-job-results.png)</sub>

The jobs list, showing the job was created and Completed:

[![Bedrock evaluations list](run-02/screenshots/01-bedrock-evaluations.png)](run-02/screenshots/01-bedrock-evaluations.png)

<sub>🔍 [Open full size](run-02/screenshots/01-bedrock-evaluations.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/01-bedrock-evaluations.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/01-bedrock-evaluations.png)</sub>

### Written observations

[`../docs/EVALUATION.md`](../docs/EVALUATION.md) — six live runs, the defects
each one surfaced, and what fixed them.

---

## Supporting infrastructure

The `create_bug_report` Lambda:

[![Lambda function](run-02/screenshots/03-lambda-create-bug-report.png)](run-02/screenshots/03-lambda-create-bug-report.png)

<sub>🔍 [Open full size](run-02/screenshots/03-lambda-create-bug-report.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/03-lambda-create-bug-report.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/03-lambda-create-bug-report.png)</sub>

Its CloudWatch log group — real invocations from the chatbot:

[![CloudWatch logs](run-02/screenshots/04-lambda-cloudwatch-logs.png)](run-02/screenshots/04-lambda-cloudwatch-logs.png)

<sub>🔍 [Open full size](run-02/screenshots/04-lambda-cloudwatch-logs.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/04-lambda-cloudwatch-logs.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/04-lambda-cloudwatch-logs.png)</sub>

Both CloudFormation stacks:

[![CloudFormation stacks](run-02/screenshots/05-cloudformation-stacks.png)](run-02/screenshots/05-cloudformation-stacks.png)

<sub>🔍 [Open full size](run-02/screenshots/05-cloudformation-stacks.png) &nbsp;·&nbsp; path: [`evidence/run-02/screenshots/05-cloudformation-stacks.png`](https://github.com/astral-fate/agentic-ai-aws-nanodegree-project-1/blob/main/evidence/run-02/screenshots/05-cloudformation-stacks.png)</sub>

**On the Lambda Test tab.** The rubric asks for a console *test invocation*
result. That needs a human to click **Test**, and automating the click would
mean the screenshot no longer shows what it claims. The CloudWatch log group
above is the substitute and is stronger — real invocations from the chatbot
rather than a synthetic console test. The equivalent test does run in the
pipeline and returns a `ticketId` with `"status": "OPEN"`.

## Files in this folder

| File | What it is |
|---|---|
| `run-02/system_prompt.txt` | The deliverable — routing, collection rules, FAQ placeholder |
| `run-02/rendered_system_prompt.txt` | The same prompt with the FAQ substituted, as uploaded |
| `run-02/online_shop_faq.md` | The FAQ, extended with a gift-card section |
| `run-02/harness-tests.json` · `run-02/flow-tests.json` | The test suite, under both names |
| `run-02/output_eval_dataset.jsonl` | 21 records, no harness errors |
| `run-02/bug_report_transcript.txt` | The multi-turn bug report |
| `run-02/dynamodb_bug_reports.json` | Full scan of the ticket table (28 items) |
| `run-02/eval-results/` | Per-record scores from Bedrock Evaluations |
| `run-02/eval_job.json` | Job ARN, name and results URI |
| `run-02/run_summary.txt` | Every ARN from the run |
| `run-02/screenshots/` | All images above |

[`../SUBMISSION.md`](../SUBMISSION.md) maps each rubric line to the AgentCore
artefact that plays the same role.
