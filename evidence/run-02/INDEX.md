# Evidence — run 02

Imported from a CloudShell `evidence.tar.gz` bundle.

```
Run summary
===========
account        : 212626318772
region         : us-east-1
caller         : arn:aws:iam::212626318772:root
model          : us.amazon.nova-pro-v1:0
judge          : amazon.nova-pro-v1:0
harness        : arn:aws:bedrock-agentcore:us-east-1:212626318772:harness/support_chatbot-2Bj15XkvH7
gateway        : arn:aws:bedrock-agentcore:us-east-1:212626318772:gateway/bug-report-tool-stack-gateway-stuq8vnpha
gateway target : bugreports  -> bugreports___create_bug_report
guardrail      : q4j8vcs1cvj9 v2
lambda         : bug-report-tool-stack-create-bug-report
table          : bug-report-tool-stack-bug-reports
eval bucket    : udacity-agentic-engineer-c1-eval-212626318772
```

## What each file proves

| File | Rubric requirement |
|---|---|
| `system_prompt.txt` | The deliverable — classification, all three routes, the collection rules |
| `rendered_system_prompt.txt` | The prompt as the harness received it, with `{{FAQ}}` substituted — the AgentCore stand-in for the 'FAQ Prompt node template showing embedded FAQ content' |
| `online_shop_faq.md` | The FAQ, extended with a gift-card section |
| `harness-tests.json` / `flow-tests.json` | Test suite, ≥1 case per route (21 total) |
| `output_eval_dataset.jsonl` | The JSONL produced by `generate-eval-dataset.py` |
| `bug_report_transcript.txt` | Multi-turn bug report with follow-up questions and the tool-call line |
| `dynamodb_bug_reports.json` | Records created in `bug-report-tool-stack-bug-reports` |
| `eval-results/` | Bedrock Evaluations output, downloaded from S3 |
| `eval_job.json` | The evaluation job ARN and name |
| `screenshots/` | Console screenshots |

See [`../../SUBMISSION.md`](../../SUBMISSION.md) for the full rubric map.
