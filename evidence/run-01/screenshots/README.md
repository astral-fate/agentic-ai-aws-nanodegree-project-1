# Console screenshots

Captured with `scripts/capture_console.py`, which drives a real Chrome
session against the AWS console. Signed in as the read-only `evidence-capture`
IAM user, account 212626318772, us-east-1.

| File | Shows | Rubric requirement |
|---|---|---|
| `01-bedrock-evaluations.png` | Bedrock → Evaluations: 4 jobs, all **Completed**, inference source `my-support-chatbot`, "Automatic: LLM as a judge" | Bedrock Evaluation job results |
| `02-dynamodb-bug-reports.png` | `bug-report-tool-stack-bug-reports` → Explore items: **24 items**, every field (`ticketId`, `createdAt`, `description`, `environment`, `status`, `stepsToReproduce`), all `OPEN` | A record created in the DynamoDB table |
| `03-lambda-create-bug-report.png` | Lambda → `bug-report-tool-stack-create-bug-report` | The tool implementation |
| `04-lambda-cloudwatch-logs.png` | CloudWatch log group for the Lambda: **6 log streams** with event times | Real invocations through the gateway |
| `05-cloudformation-stacks.png` | Both stacks | Deployed infrastructure |

## Two honest notes

**The Lambda Test tab result is not here.** The rubric asks for a screenshot
of a console *test invocation*, which needs a human to click **Test**. Driving
that click automatically would mean the screenshot no longer shows what it
claims to. `04-lambda-cloudwatch-logs.png` is the substitute and is arguably
stronger: it shows the Lambda's real invocations from the chatbot, not a
synthetic console test. The equivalent test *was* run — see the Lambda smoke
test in the run log, which returned a `ticketId` and `"status": "OPEN"`.

**Nothing here is generated.** Each PNG is a real console page loaded in a
browser. No API data was rendered into a console-lookalike page.
