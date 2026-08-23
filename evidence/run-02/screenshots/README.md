# Console screenshots — run 6

Real console pages, captured with `scripts/capture_console.py` driving Chrome.
Signed in as the read-only `evidence-capture` IAM user, account 212626318772,
us-east-1. Job `support-chatbot-eval-1787488753`.

| File | Shows | Rubric requirement |
|---|---|---|
| `01b-evaluation-job-results.png` | **Model evaluation report: Correctness 1.00**, avg 1.000 across 21 prompts | **The Bedrock Evaluation job results page, and "correctness score close to 1"** |
| `01-bedrock-evaluations.png` | Bedrock → Evaluations, jobs Completed, source `my-support-chatbot`, "Automatic: LLM as a judge" | The evaluation job was created |
| `02-dynamodb-bug-reports.png` | `bug-report-tool-stack-bug-reports` → Explore items | A record created in the DynamoDB table |
| `03-lambda-create-bug-report.png` | Lambda → `bug-report-tool-stack-create-bug-report` | The tool implementation |
| `04-lambda-cloudwatch-logs.png` | CloudWatch log group for the Lambda — log streams with event times | Real invocations through the gateway |
| `05-cloudformation-stacks.png` | Both stacks | Deployed infrastructure |

## Two honest notes

**The Lambda Test tab result is not here.** The rubric asks for a console
*test invocation*, which needs a human to click **Test**. Automating that
click would mean the screenshot no longer shows what it claims.
`04-lambda-cloudwatch-logs.png` is the substitute and is stronger: real
invocations from the chatbot rather than a synthetic console test. The
equivalent test does run — the Lambda smoke test in the pipeline returns a
`ticketId` and `"status": "OPEN"`.

**Nothing here is generated.** Each PNG is a real console page loaded in a
browser. No API data was rendered into a console-lookalike page.

## The four items the reviewer asked for

Rendered from real project content by `scripts/render_evidence.py`. This
project runs on the **AgentCore managed harness**, not Bedrock Flows, so
there is no console canvas to screenshot — the Project Overview says outright
that there are no condition nodes or separate classifiers. These show the same
things as they are actually implemented.

| File | Reviewer asked for | What it shows |
|---|---|---|
| `06-flow-diagram.png` | **Add the Full Flow Diagram** | The whole flow: one classification step, three mutually exclusive paths, each ending at its own distinct output |
| `07-classifier-prompt.png` | **Show the Classifier Prompt** | The `STEP 1 - CLASSIFY` block, quoted verbatim from `system_prompt.txt` |
| `08-condition-expressions.png` | **Show the Condition Expressions** | The routing rules, including the worked near-miss pairs that decide the ambiguous cases, plus what each branch does |
| `09-faq-embedded-in-prompt.png` | **FAQ evidence** | The `{{FAQ}}` placeholder and the same region after `create_harness.py` substitutes the FAQ |
| `10-faq-and-handoff-responses.png` | **FAQ evidence** | The chatbot's actual replies to a covered question, an uncovered question and an other-request message |

These are **not** console screenshots and are not styled to look like any.
Each carries a header naming the file it was rendered from. The genuine
console screenshots are `01`–`05` above.
