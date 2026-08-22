# Runbook

Every command runs from `project/starter/`, in **`us-east-1`**. Some smaller
regions do not have all AgentCore features, and every script and template in
the project assumes that region.

## 0. Prerequisites

```bash
aws --version                 # install the CLI if this fails
aws sts get-caller-identity   # confirms which account you are in

python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -c "import boto3; print(boto3.__version__)"   # needs 1.43+
```

`boto3` below 1.43 does not have the AgentCore harness APIs. The course pins
`boto3==1.43.76` in `project/starter/requirements.txt`.

Also confirm you have **Amazon Nova Pro** model access in the Bedrock console.
The project pins `us.amazon.nova-pro-v1:0` everywhere on purpose — the harness
default model needs an AWS Marketplace subscription that lab accounts cannot
complete.

## 1. Deploy the tool stack

```bash
aws cloudformation deploy \
  --template-file cloudformation-tool.yaml \
  --stack-name bug-report-tool-stack \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

`CAPABILITY_NAMED_IAM` is required because the template creates named roles.

Check the outputs:

```bash
aws cloudformation describe-stacks --stack-name bug-report-tool-stack \
  --query 'Stacks[0].Outputs' --output table --region us-east-1
```

## 2. Verify the Lambda on its own

Before wiring it into a prompt, confirm the tool works in isolation. In the
Lambda console open `bug-report-tool-stack-create-bug-report` → **Test**, and
use this event (the gateway sends arguments directly, with no envelope):

```json
{
  "description": "The checkout page crashes when I click the Pay button",
  "stepsToReproduce": "1. Add an item to the cart. 2. Go to checkout. 3. Click Pay.",
  "environment": "Chrome 120 on macOS Sonoma"
}
```

Expect `{"ticketId": "...", "status": "OPEN"}`. Then confirm the row landed:

```bash
aws dynamodb scan --table-name bug-report-tool-stack-bug-reports --region us-east-1
```

| Symptom | Cause |
|---|---|
| `AccessDeniedException` | The IAM policy is on the wrong execution role |
| `ResourceNotFoundException` | The Lambda's `TABLE_NAME` doesn't match the table |
| Anything else | `/aws/lambda/bug-report-tool-stack-create-bug-report` in CloudWatch — the handler prints every event it receives |

## 3. Create the gateway

```bash
python setup_gateway.py
```

Reads the stack outputs itself and writes `agentcore_config.json`.

If it fails immediately after the stack finishes with an access or validation
error mentioning the role, that is IAM propagation delay. The script already
retries; if it still fails, wait a minute and run it again.

The target is named `bugreports`, so the model sees the tool as
`bugreports___create_bug_report`. **Target names may only contain letters,
digits and underscores** — a dash breaks Nova tool calling.

## 4. Create the harness

```bash
python create_harness.py        # first run takes ~2-3 minutes
```

Reads `system_prompt.txt`, substitutes `{{FAQ}}` with `online_shop_faq.md`,
pins Nova Pro with greedy decoding (temperature 0, topK 1 — AWS's
recommendation for reliable tool calling), waits for `READY`, and records the
harness ARN in `agentcore_config.json`.

Re-running it **updates** the existing harness, which is the whole iteration
loop: edit the prompt → re-run → new `chat.py` session. There is no prepare
step and nothing to redeploy.

## 5. Chat with it

```bash
python chat.py            # --verbose to dump raw stream events
```

Each run is one conversation. Try all three routes:

```
you> Your checkout page crashes when I click Pay
        → should acknowledge and ask ONE follow-up question

you> How long do I have to return something?
        → should answer "30 days", from the FAQ

you> Can you recommend a good pizza place?
        → should hand off to 1-800-555-0199
```

Walk a bug report all the way through and watch for:

```
[tool call] bugreports___create_bug_report
```

If that line never appears, the prompt is not telling the model clearly enough
when to use the tool. Confirm the ticket landed:

```bash
aws dynamodb scan --table-name bug-report-tool-stack-bug-reports --region us-east-1
```

## 6. Deploy the testing stack

```bash
aws cloudformation deploy \
  --template-file cloudformation-testing.yaml \
  --stack-name bug-report-testing-stack \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-east-1
```

## 7. Generate the eval dataset

```bash
python generate-eval-dataset.py --tests-json harness-tests.json
```

One harness call per test case, each in a fresh session, written to
`output_eval_dataset.jsonl`. Any line whose `response` starts with
`[HARNESS_ERROR]` means that call failed — check the terminal output.

## 8. Run the evaluation

```bash
python run_evaluation.py --wait
```

Validates the dataset, uploads it, and creates the job — reading the bucket
and role ARN from the testing stack so there is nothing to paste.

<details>
<summary>The equivalent manual commands</summary>

```bash
aws s3 cp output_eval_dataset.jsonl \
  s3://udacity-agentic-engineer-c1-eval-<ACCOUNT_ID>/output_eval_dataset.jsonl \
  --region us-east-1

aws bedrock create-evaluation-job \
  --job-name support-chatbot-eval-run-1 \
  --role-arn <BedrockEvalRoleArn> \
  --evaluation-config '{"automated":{"datasetMetricConfigs":[{"taskType":"General","dataset":{"name":"support-chatbot-eval-dataset","datasetLocation":{"s3Uri":"s3://<BUCKET>/output_eval_dataset.jsonl"}},"metricNames":["Builtin.Correctness"]}],"evaluatorModelConfig":{"bedrockEvaluatorModels":[{"modelIdentifier":"amazon.nova-pro-v1:0"}]}}}' \
  --inference-config '{"models":[{"precomputedInferenceSource":{"inferenceSourceIdentifier":"my-support-chatbot"}}]}' \
  --output-data-config '{"s3Uri":"s3://<BUCKET>/results/"}' \
  --region us-east-1
```

`inferenceSourceIdentifier` **must** equal the `modelIdentifier` in the JSONL
(`my-support-chatbot` by default), or the job scores nothing.
</details>

View results in the Bedrock console → **Evaluations**, then record what you
find in [`EVALUATION.md`](EVALUATION.md).

## 9. Iterate

If a category scores badly:

1. Edit `system_prompt.txt`
2. `python create_harness.py`
3. `python generate-eval-dataset.py --tests-json harness-tests.json`
4. `python run_evaluation.py --wait`

Run `python -m pytest` from the repo root first — it catches a broken
`{{FAQ}}` placeholder or a lost route in two seconds, before you spend three
minutes on a harness update.

The usual fixes: sharpen the category definitions, tighten the "answer only
from the FAQ" instruction, or spell out the bug-report checklist in more
detail.

## 10. Tear down

Order matters — the harness holds the gateway, and CloudFormation cannot
delete a non-empty bucket.

```bash
python cleanup_agentcore.py       # harness → target → gateway

aws s3 rm s3://udacity-agentic-engineer-c1-eval-<ACCOUNT_ID> --recursive --region us-east-1
aws cloudformation delete-stack --stack-name bug-report-testing-stack --region us-east-1
aws cloudformation delete-stack --stack-name bug-report-tool-stack --region us-east-1

rm -rf venv                       # optional
```

If the testing stack is already in `DELETE_FAILED`, empty the bucket and run
its `delete-stack` again.
