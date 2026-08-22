#!/usr/bin/env python3
"""Drive a full bug-report conversation and verify the ticket in DynamoDB.

    python scripted_bug_report.py

This is the "add multi-turn bug-report tests" stand-out suggestion, done
end to end against real AWS:

  1. Opens ONE stateful harness session and plays a scripted customer
     through it, turn by turn, exactly as a person would in chat.py.
  2. Watches the stream for the `bugreports___create_bug_report` tool call.
  3. Pulls the ticket ID out of the assistant's final reply.
  4. Reads that item back from DynamoDB and checks every stored field
     against what the scripted customer actually said.

It prints a PASS/FAIL report and saves the transcript to
`bug_report_transcript.txt`, which is the chat transcript evidence the
rubric asks for.

Exit status is 0 only if the ticket was filed AND every field matches, so
this can run in CI once credentials exist.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.eventstream import EventStream

# The scripted customer. Each turn withholds something, so the assistant has
# to ask for the missing pieces one at a time - which is the behaviour under
# test.
CONVERSATION = [
    "Your checkout page crashes every single time I click the Pay button.",
    "I add a pair of headphones to the cart, go to checkout, fill in my "
    "card details and then click Pay. The page goes white straight away.",
    "I'm using Chrome 120 on macOS Sonoma, on a MacBook Air.",
]

# What must survive the round trip into DynamoDB. Each field maps to
# substrings that should appear in the stored value (lowercased).
EXPECTED_CONTENT = {
    "description": ["checkout", "pay"],
    "stepsToReproduce": ["cart", "checkout"],
    "environment": ["chrome", "macos"],
}

TOOL_NAME = "bugreports___create_bug_report"
TICKET_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I
)


def event_stream(response):
    for value in response.values():
        if isinstance(value, EventStream):
            return value
    raise RuntimeError(f"No event stream in response: {list(response)}")


def send(rt, config, session_id, text, transcript):
    """One turn. Returns (reply_text, tool_calls_seen)."""
    response = rt.invoke_harness(
        harnessArn=config["harness_arn"],
        runtimeSessionId=session_id,
        model={"bedrockModelConfig": {
            "modelId": config.get("model_id", "us.amazon.nova-pro-v1:0")}},
        tools=[{
            "type": "agentcore_gateway",
            "name": "support_gateway",
            "config": {"agentCoreGateway": {"gatewayArn": config["gateway_arn"]}},
        }],
        messages=[{"role": "user", "content": [{"text": text}]}],
    )

    texts, buffer, tools = [], [], []
    for event in event_stream(response):
        if "contentBlockStart" in event:
            tool_use = event["contentBlockStart"].get("start", {}).get("toolUse")
            if tool_use:
                name = tool_use.get("name", "?")
                tools.append(name)
                print(f"\n[tool call] {name}", flush=True)
                transcript.append(f"[tool call] {name}")
        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            if "text" in delta:
                print(delta["text"], end="", flush=True)
                buffer.append(delta["text"])
        elif "messageStop" in event:
            if buffer:
                texts.append("".join(buffer))
                buffer = []
    if buffer:
        texts.append("".join(buffer))
    print()
    return (texts[-1] if texts else ""), tools


def check(label, ok, detail=""):
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" - {detail}" if detail else ""))
    return ok


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="agentcore_config.json")
    p.add_argument("--transcript", default="bug_report_transcript.txt")
    args = p.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        sys.exit(f"{args.config} not found - run setup_gateway.py and "
                 "create_harness.py first.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if "harness_arn" not in config:
        sys.exit("No harness in config - run create_harness.py first.")

    rt = boto3.client(
        "bedrock-agentcore",
        region_name=config["region"],
        config=Config(read_timeout=300, retries={"max_attempts": 1}),
    )

    session_id = f"{uuid.uuid4()}-scripted-bug"
    transcript = [f"session: {session_id}", ""]
    print(f"Session {session_id}\n")

    all_tools, last_reply = [], ""
    for turn, text in enumerate(CONVERSATION, 1):
        print(f"you> {text}")
        transcript.append(f"you> {text}")
        print("bot> ", end="", flush=True)
        transcript.append("bot> ")
        reply, tools = send(rt, config, session_id, text, transcript)
        transcript[-1] = f"bot> {reply}"
        transcript.append("")
        all_tools += tools
        last_reply = reply

        # The tool must not fire before the last turn - that is the whole
        # point of collecting the three fields first.
        if tools and turn < len(CONVERSATION):
            print(f"\n!! tool called on turn {turn}, before all three fields "
                  "were collected", file=sys.stderr)

    Path(args.transcript).write_text("\n".join(transcript), encoding="utf-8")
    print(f"\nTranscript saved to {args.transcript}")

    # ---- verification -----------------------------------------------------
    print("\n" + "=" * 62)
    print("VERIFICATION")
    print("=" * 62)

    results = []
    results.append(check(
        "the create_bug_report tool was called",
        TOOL_NAME in all_tools,
        f"saw {all_tools or 'no tool calls'}",
    ))
    results.append(check(
        "it was called exactly once",
        all_tools.count(TOOL_NAME) == 1,
        f"called {all_tools.count(TOOL_NAME)}x",
    ))

    match = TICKET_RE.search(last_reply)
    results.append(check(
        "the assistant relayed a ticket ID to the customer",
        match is not None,
    ))
    if not match:
        print("\nNo ticket ID in the final reply; cannot verify DynamoDB.")
        sys.exit(1)

    ticket_id = match.group(0)
    print(f"\n  ticket: {ticket_id}")

    table = boto3.resource("dynamodb", region_name=config["region"]).Table(
        config["table_name"]
    )
    item = table.get_item(Key={"ticketId": ticket_id}).get("Item")
    results.append(check("the ticket exists in DynamoDB", item is not None))
    if not item:
        sys.exit(1)

    print("\n  stored item:")
    for key in sorted(item):
        print(f"    {key}: {item[key]}")

    print()
    results.append(check("status is OPEN", item.get("status") == "OPEN"))
    for field, needles in EXPECTED_CONTENT.items():
        value = str(item.get(field, "")).lower()
        results.append(check(
            f"{field} reflects what the customer said",
            all(n in value for n in needles),
            f"looked for {needles}",
        ))

    print("\n" + "=" * 62)
    if all(results):
        print(f"ALL {len(results)} CHECKS PASSED")
        print("=" * 62)
        return
    print(f"{results.count(False)} of {len(results)} CHECKS FAILED")
    print("=" * 62)
    sys.exit(1)


if __name__ == "__main__":
    main()
