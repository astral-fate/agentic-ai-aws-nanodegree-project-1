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
