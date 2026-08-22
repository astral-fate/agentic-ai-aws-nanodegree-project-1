#!/usr/bin/env python3
"""Upload the eval dataset and start a Bedrock Evaluations job.

    python run_evaluation.py --wait

This is a convenience wrapper around the two manual steps in the Testing
Framework page - `aws s3 cp` followed by a long `aws bedrock
create-evaluation-job` command with hand-written JSON. It reads the bucket
name and role ARN straight from the testing stack's outputs, so there is
nothing to copy and paste and no chance of the
`inferenceSourceIdentifier` drifting away from the `modelIdentifier` in the
JSONL (a mismatch there makes the job score nothing at all).

Prerequisites:
  * cloudformation-testing.yaml deployed  (stack: bug-report-testing-stack)
  * output_eval_dataset.jsonl generated   (generate-eval-dataset.py)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import boto3

DEFAULT_REGION = "us-east-1"


def stack_outputs(stack_name: str, region: str) -> dict:
    cfn = boto3.client("cloudformation", region_name=region)
    stacks = cfn.describe_stacks(StackName=stack_name)["Stacks"]
    return {o["OutputKey"]: o["OutputValue"] for o in stacks[0].get("Outputs", [])}


def check_dataset(path: Path, model_identifier: str) -> int:
    """Fail fast on the mistakes that only surface after the job runs."""
    if not path.exists():
        sys.exit(f"{path} not found - run generate-eval-dataset.py first.")

    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        sys.exit(f"{path} is empty.")

    errors = []
    for n, line in enumerate(lines, 1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"line {n}: not valid JSON ({exc})")
            continue

        missing = {"prompt", "referenceResponse", "modelResponses"} - set(record)
        if missing:
            errors.append(f"line {n}: missing {sorted(missing)}")
            continue

        responses = record["modelResponses"]
        if not isinstance(responses, list) or not responses:
            errors.append(f"line {n}: modelResponses must be a non-empty list")
            continue

        got = responses[0].get("modelIdentifier")
        if got != model_identifier:
            errors.append(
                f"line {n}: modelIdentifier is {got!r} but the job will look "
                f"for {model_identifier!r}"
            )
        if str(responses[0].get("response", "")).startswith("[HARNESS_ERROR]"):
            errors.append(f"line {n}: response is a harness error, not a reply")

    if errors:
        print("Dataset problems found:", file=sys.stderr)
        for err in errors[:20]:
            print(f"  - {err}", file=sys.stderr)
        sys.exit("Fix the dataset and re-run.")

    return len(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dataset", default="output_eval_dataset.jsonl",
                   help="JSONL produced by generate-eval-dataset.py.")
    p.add_argument("--testing-stack", default="bug-report-testing-stack",
                   help="Stack deployed from cloudformation-testing.yaml.")
    p.add_argument("--job-name", default=None,
                   help="Evaluation job name (default: support-chatbot-eval-<n>).")
    p.add_argument("--model-identifier", default="my-support-chatbot",
                   help="Must match modelIdentifier in the JSONL.")
    p.add_argument("--evaluator-model", default="amazon.nova-pro-v1:0",
                   help="Model that acts as the judge.")
    p.add_argument("--metrics", default="Builtin.Correctness",
                   help="Comma-separated Bedrock Evaluations metric names.")
    p.add_argument("--region", default=DEFAULT_REGION)
    p.add_argument("--wait", action="store_true",
                   help="Poll until the job finishes.")
    args = p.parse_args()

    dataset = Path(args.dataset)
    n_records = check_dataset(dataset, args.model_identifier)
    print(f"{dataset} looks well-formed ({n_records} records).")

    print(f"Reading outputs of stack '{args.testing_stack}'...")
    outputs = stack_outputs(args.testing_stack, args.region)
    bucket = outputs["EvalDatasetBucketName"]
    role_arn = outputs["BedrockEvalRoleArn"]

    key = dataset.name
    print(f"Uploading to s3://{bucket}/{key} ...")
    boto3.client("s3", region_name=args.region).upload_file(
        str(dataset), bucket, key
    )

    job_name = args.job_name or f"support-chatbot-eval-{int(time.time())}"
    metrics = [m.strip() for m in args.metrics.split(",") if m.strip()]

    print(f"Creating evaluation job '{job_name}' ...")
    bedrock = boto3.client("bedrock", region_name=args.region)
    response = bedrock.create_evaluation_job(
        jobName=job_name,
        roleArn=role_arn,
        evaluationConfig={
            "automated": {
                "datasetMetricConfigs": [
                    {
                        "taskType": "General",
                        "dataset": {
                            "name": "support-chatbot-eval-dataset",
                            "datasetLocation": {
                                "s3Uri": f"s3://{bucket}/{key}"
                            },
                        },
                        "metricNames": metrics,
                    }
                ],
                "evaluatorModelConfig": {
                    "bedrockEvaluatorModels": [
                        {"modelIdentifier": args.evaluator_model}
                    ]
                },
            }
        },
        inferenceConfig={
            "models": [
                {
                    "precomputedInferenceSource": {
                        "inferenceSourceIdentifier": args.model_identifier
                    }
                }
            ]
        },
        # One prefix per job. A shared results/ prefix accumulates every run
        # ever made, so anything reading it back averages the current run
        # together with all its predecessors - which silently misreported the
        # correctness score across three runs before it was caught.
        outputDataConfig={"s3Uri": f"s3://{bucket}/results/{job_name}/"},
    )

    job_arn = response["jobArn"]
    results_uri = f"s3://{bucket}/results/{job_name}/"
    print(f"\nJob created.\n  arn:     {job_arn}")
    print(f"  results: {results_uri}")
    print("  console: Amazon Bedrock -> Evaluations")

    # Recorded so the caller can fetch exactly this job's results rather than
    # everything ever written under results/.
    Path("eval_job.json").write_text(
        json.dumps(
            {
                "jobArn": job_arn,
                "jobName": job_name,
                "bucket": bucket,
                "resultsUri": results_uri,
                "resultsPrefix": f"results/{job_name}/",
                "evaluatorModel": args.evaluator_model,
                "metrics": metrics,
                "records": n_records,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if not args.wait:
        print("\nRe-run with --wait to poll until it finishes.")
        return

    print("\nWaiting for the job to finish...")
    while True:
        status = bedrock.get_evaluation_job(jobIdentifier=job_arn)["status"]
        if status in ("Completed", "Failed", "Stopped"):
            print(f"  final status: {status}")
            if status != "Completed":
                sys.exit(f"Evaluation job ended as {status}.")
            break
        print(f"  status: {status} - waiting...")
        time.sleep(30)

    print(f"\nDone. Download the scores with:\n"
          f"  aws s3 cp {results_uri} . --recursive --region {args.region}")


if __name__ == "__main__":
    main()
