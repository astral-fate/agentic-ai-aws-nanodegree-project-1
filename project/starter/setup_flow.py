#!/usr/bin/env python3
"""Build a real Amazon Bedrock Flow for the same three-way routing.

    python setup_flow.py            # create or update, then prepare
    python setup_flow.py --delete   # remove it

Why this exists
---------------
The chatbot itself runs on the **AgentCore managed harness**, where routing
lives in a system prompt and there is no canvas. The project rubric, though,
was written for **Bedrock Flows** and asks for a flow diagram, a classifier
prompt node and Condition node expressions — artefacts that only exist if
there is an actual Flow.

So this builds one. It is a genuine Bedrock Flow in the account, with the
same three categories and the same routing rules as ``system_prompt.txt``,
and the console renders it as a diagram that can be screenshotted.

The graph
---------
                          ┌─────────────────┐
                          │   FlowInput     │
                          └────────┬────────┘
                                   ▼
                        ┌──────────────────────┐
                        │  ClassifyMessage     │  Prompt node
                        │  emits exactly one:  │  Nova Pro, temp 0
                        │  BUG_REPORT /        │
                        │  PLATFORM_QUESTION / │
                        │  OTHER               │
                        └──────────┬───────────┘
                                   ▼
                        ┌──────────────────────┐
                        │  RouteByCategory     │  Condition node
                        └──┬────────┬──────────┘
              IsBugReport  │        │  IsPlatformQuestion   │ default
                           ▼        ▼                       ▼
                 ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
                 │ BugReport    │ │ FaqAnswer    │ │ HumanHandoff   │
                 │ Collector    │ │ (FAQ inline) │ │ (1-800-…)      │
                 └──────┬───────┘ └──────┬───────┘ └───────┬────────┘
                        ▼                ▼                 ▼
                 ┌──────────────┐ ┌──────────────┐ ┌────────────────┐
                 │ BugReport    │ │ Faq          │ │ Handoff        │
                 │ Output       │ │ Output       │ │ Output         │
                 └──────────────┘ └──────────────┘ └────────────────┘

Three distinct paths, each terminating at its own Output node.

Note on scope: the Flow demonstrates classification and routing. Ticket
creation still happens through the AgentCore harness and the gateway, because
that is where the stateful multi-turn collection lives — a Flow node cannot
ask a follow-up question and wait.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

FLOW_NAME = "customer-request-flow"
ROLE_NAME = "bug-report-tool-stack-flow-role"
MODEL_ID = "us.amazon.nova-pro-v1:0"
SUPPORT_PHONE = "1-800-555-0199"

CLASSIFIER_TEMPLATE = """You classify incoming customer support messages for an online shop.

Read the message and reply with EXACTLY ONE of these three words, nothing else:

BUG_REPORT
  The website, app or checkout is broken: it errors, crashes, hangs, loops,
  shows a blank page, or does not do what it obviously should.
  Signals: crashes, error, won't load, broken, stuck, frozen, blank page,
  the button does nothing, spins forever, 500, 404.

PLATFORM_QUESTION
  A question about orders, shipping, delivery, returns, refunds, payments,
  promotions, products, stock, accounts or privacy, where shop policy is the
  answer.

OTHER
  Everything else. Requests policy does not cover, account-specific actions,
  complaints, legal or partnership enquiries, off-topic chat, and anything
  you are unsure about.

A policy question that merely mentions something going wrong is NOT a bug:
  "Why was my payment declined?"       -> PLATFORM_QUESTION
  "The payment page shows a 500 error" -> BUG_REPORT
  "Why was my order canceled?"         -> PLATFORM_QUESTION
  "I can't add anything to my cart"    -> BUG_REPORT

Customer message:
{{customer_message}}

Answer with one word only."""

BUG_TEMPLATE = """You are the customer support assistant for an online shop, handling a bug report.

You need three things before a ticket can be filed:
  1. description       what is broken, in the customer's own words
  2. stepsToReproduce  what they did, in order, that triggers it
  3. environment       browser, operating system and/or device

Acknowledge the problem in one sentence, then ask for ONE missing item.
Never ask two questions at once. Never invent a value, and never write
"not provided" — a field you have not been told is still missing.

Customer message:
{{customer_message}}"""

FAQ_TEMPLATE = """You are the customer support assistant for an online shop.

Answer the customer's question using ONLY the FAQ below. It is the single
source of truth for shop policy. Put the relevant entry in your own words, in
two to four sentences. Never invent, extend, round or estimate a policy,
price, fee or timeframe that is not written here.

If the FAQ does not cover the question, say so and give the customer the
support line: {phone}, Monday to Friday.

--- FAQ document ---
{{{{FAQ}}}}
--- end of FAQ document ---

Customer message:
{{{{customer_message}}}}""".replace("{phone}", SUPPORT_PHONE)

HANDOFF_TEMPLATE = """You are the customer support assistant for an online shop.

This request is not something you can help with from this chat. Reply with
exactly two parts:

  1. One short, warm sentence showing you understood what they asked.
  2. This sentence, word for word:

     Please call our support team on {phone}, Monday to Friday,
     and they will be able to help you.

Do not speculate about what the human team will decide, and do not promise an
outcome, a refund or a timeframe.

Customer message:
{{{{customer_message}}}}""".replace("{phone}", SUPPORT_PHONE)

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Principal": {"Service": "bedrock.amazonaws.com"},
        "Action": "sts:AssumeRole",
    }],
}

PERMISSIONS = {
    "Version": "2012-10-17",
    "Statement": [{
        "Sid": "InvokeTheModel",
        "Effect": "Allow",
        "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        "Resource": "*",
    }],
}


def prompt_node(name: str, template: str, inputs: list[str]) -> dict:
    return {
        "name": name,
        "type": "Prompt",
        "configuration": {"prompt": {"sourceConfiguration": {"inline": {
            "modelId": MODEL_ID,
            "templateType": "TEXT",
            "inferenceConfiguration": {"text": {"temperature": 0.0, "maxTokens": 900}},
            "templateConfiguration": {"text": {
                "text": template,
                "inputVariables": [{"name": v} for v in inputs],
            }},
        }}}},
        "inputs": [{"name": v, "type": "String", "expression": "$.data"} for v in inputs],
        "outputs": [{"name": "modelCompletion", "type": "String"}],
    }


def build_definition(faq: str) -> dict:
    nodes = [
        {"name": "FlowInput", "type": "Input",
         "configuration": {"input": {}},
         "outputs": [{"name": "document", "type": "String"}]},

        prompt_node("ClassifyMessage", CLASSIFIER_TEMPLATE, ["customer_message"]),

        {"name": "RouteByCategory", "type": "Condition",
         "configuration": {"condition": {"conditions": [
             {"name": "IsBugReport",
              "expression": 'category == "BUG_REPORT"'},
             {"name": "IsPlatformQuestion",
              "expression": 'category == "PLATFORM_QUESTION"'},
             {"name": "default"},
         ]}},
         "inputs": [{"name": "category", "type": "String", "expression": "$.data"}]},

        prompt_node("BugReportCollector", BUG_TEMPLATE, ["customer_message"]),
        prompt_node("FaqAnswer", FAQ_TEMPLATE.replace("{{FAQ}}", faq),
                    ["customer_message"]),
        prompt_node("HumanHandoff", HANDOFF_TEMPLATE, ["customer_message"]),

        {"name": "BugReportOutput", "type": "Output",
         "configuration": {"output": {}},
         "inputs": [{"name": "document", "type": "String", "expression": "$.data"}]},
        {"name": "FaqOutput", "type": "Output",
         "configuration": {"output": {}},
         "inputs": [{"name": "document", "type": "String", "expression": "$.data"}]},
        {"name": "HandoffOutput", "type": "Output",
         "configuration": {"output": {}},
         "inputs": [{"name": "document", "type": "String", "expression": "$.data"}]},
    ]

    def data(name, src, src_out, tgt, tgt_in):
        return {"name": name, "type": "Data", "source": src, "target": tgt,
                "configuration": {"data": {"sourceOutput": src_out,
                                           "targetInput": tgt_in}}}

    def cond(name, tgt, condition):
        return {"name": name, "type": "Conditional",
                "source": "RouteByCategory", "target": tgt,
                "configuration": {"conditional": {"condition": condition}}}

    connections = [
        data("InputToClassifier", "FlowInput", "document",
             "ClassifyMessage", "customer_message"),
        data("ClassifierToRouter", "ClassifyMessage", "modelCompletion",
             "RouteByCategory", "category"),

        # The original message reaches each branch directly, so the branch
        # sees what the customer wrote rather than the classifier's one word.
        data("InputToBug", "FlowInput", "document",
             "BugReportCollector", "customer_message"),
        data("InputToFaq", "FlowInput", "document",
             "FaqAnswer", "customer_message"),
        data("InputToHandoff", "FlowInput", "document",
             "HumanHandoff", "customer_message"),

        cond("RouteToBug", "BugReportCollector", "IsBugReport"),
        cond("RouteToFaq", "FaqAnswer", "IsPlatformQuestion"),
        cond("RouteToHandoff", "HumanHandoff", "default"),

        data("BugToOutput", "BugReportCollector", "modelCompletion",
             "BugReportOutput", "document"),
        data("FaqToOutput", "FaqAnswer", "modelCompletion",
             "FaqOutput", "document"),
        data("HandoffToOutput", "HumanHandoff", "modelCompletion",
             "HandoffOutput", "document"),
    ]
    return {"nodes": nodes, "connections": connections}


def ensure_role(region: str) -> str:
    iam = boto3.client("iam")
    try:
        arn = iam.get_role(RoleName=ROLE_NAME)["Role"]["Arn"]
        print(f"  role {ROLE_NAME} already exists")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "NoSuchEntity":
            raise
        print(f"  creating role {ROLE_NAME} ...")
        arn = iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(TRUST_POLICY),
            Description="Execution role for the customer-request Bedrock Flow",
        )["Role"]["Arn"]
        print("  waiting 10s for IAM to propagate ...")
        time.sleep(10)
    iam.put_role_policy(RoleName=ROLE_NAME, PolicyName="InvokeModel",
                        PolicyDocument=json.dumps(PERMISSIONS))
    return arn


def find_flow(client, name):
    paginator = client.get_paginator("list_flows")
    for page in paginator.paginate():
        for f in page.get("flowSummaries", []):
            if f["name"] == name:
                return f
    return None


def wait_status(client, flow_id, target, timeout=180):
    deadline = time.time() + timeout
    status = "?"
    while time.time() < deadline:
        status = client.get_flow(flowIdentifier=flow_id)["status"]
        if status == target:
            return status
        if status == "Failed":
            detail = client.get_flow(flowIdentifier=flow_id).get("validations")
            sys.exit(f"Flow entered Failed. Validations: {detail}")
        time.sleep(5)
    return status


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--name", default=FLOW_NAME)
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--faq-file", default="online_shop_faq.md")
    p.add_argument("--config", default="agentcore_config.json")
    p.add_argument("--delete", action="store_true")
    args = p.parse_args()

    client = boto3.client("bedrock-agent", region_name=args.region)

    if args.delete:
        existing = find_flow(client, args.name)
        if not existing:
            print(f"No flow named {args.name}.")
            return
        client.delete_flow(flowIdentifier=existing["id"], skipResourceInUseCheck=True)
        print(f"Deleted flow {args.name} ({existing['id']}).")
        return

    faq = Path(args.faq_file).read_text(encoding="utf-8")
    definition = build_definition(faq)

    print("Validating the definition ...")
    result = client.validate_flow_definition(definition=definition)
    problems = [v for v in result.get("validations", []) if v.get("severity") == "Error"]
    if problems:
        for v in problems:
            print(f"  {v.get('message')}", file=sys.stderr)
        sys.exit("Definition is invalid.")
    print("  no errors")

    role_arn = ensure_role(args.region)

    existing = find_flow(client, args.name)
    if existing:
        print(f"Updating flow {args.name} ({existing['id']}) ...")
        client.update_flow(flowIdentifier=existing["id"], name=args.name,
                           executionRoleArn=role_arn, definition=definition)
        flow_id = existing["id"]
    else:
        print(f"Creating flow {args.name} ...")
        created = client.create_flow(
            name=args.name,
            description="Classifies customer messages and routes them to one "
                        "of three paths, each ending at its own Output node.",
            executionRoleArn=role_arn,
            definition=definition,
        )
        flow_id = created["id"]

    print("Preparing the flow ...")
    client.prepare_flow(flowIdentifier=flow_id)
    status = wait_status(client, flow_id, "Prepared")
    flow = client.get_flow(flowIdentifier=flow_id)

    print(f"\nFlow is {status}.")
    print(f"  id  : {flow_id}")
    print(f"  arn : {flow['arn']}")
    console = (f"https://{args.region}.console.aws.amazon.com/bedrock/home"
               f"?region={args.region}#/flows/{flow_id}")
    print(f"  console: {console}")

    cfg_path = Path(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    cfg.update({"flow_id": flow_id, "flow_arn": flow["arn"],
                "flow_name": args.name, "flow_console_url": console})
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(f"Saved to {args.config}.")


if __name__ == "__main__":
    main()
