#!/usr/bin/env python3
"""chat.py, with a Bedrock Guardrail screening every message first.

    python setup_guardrail.py      # once
    python chat_guarded.py

Identical to ``chat.py`` except for one step: each message is run through
``bedrock-runtime:ApplyGuardrail`` **before** ``invoke_harness`` is called.
A blocked message never reaches Nova Pro at all - no tokens are spent and
no tool can be triggered by it.

That ordering is the point of the stand-out suggestion: the system prompt's
injection defences work by persuading the model to refuse, which means the
model has already read the attack. The guardrail stops it earlier.

The turn is still recorded in the transcript, so the conversation stays
coherent; the customer simply gets the refusal message.

Run ``chat.py`` instead for the unguarded behaviour - the starter file is
unchanged.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

import boto3
from botocore.config import Config

import chat  # the unmodified starter client - reuse its streaming invoke
import guardrail


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="agentcore_config.json")
    parser.add_argument("--verbose", action="store_true",
                        help="Print every raw stream event.")
    parser.add_argument("--show-assessments", action="store_true",
                        help="Print why the guardrail blocked something.")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if "harness_arn" not in config:
        sys.exit("No harness in config yet - run create_harness.py first.")
    if not guardrail.is_configured(config):
        sys.exit("No guardrail in config yet - run setup_guardrail.py first.")

    session_id = f"{uuid.uuid4()}-guarded-chat"

    rt = boto3.client(
        "bedrock-agentcore",
        region_name=config["region"],
        config=Config(read_timeout=300, retries={"max_attempts": 1}),
    )
    br = boto3.client("bedrock-runtime", region_name=config["region"])

    print(f"Connected to harness {config.get('harness_name', '?')} "
          f"(session {session_id}).")
    print(f"Guardrail {config['guardrail_id']} v{config['guardrail_version']} "
          "screening every message.")
    print("Type a message, or 'quit' to exit.\n")

    blocked = 0
    while True:
        try:
            user_text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_text:
            continue
        if user_text.lower() in ("quit", "exit"):
            break

        verdict = guardrail.screen(
            br, user_text,
            config["guardrail_id"], config["guardrail_version"],
        )
        if not verdict.allowed:
            blocked += 1
            print("\n[guardrail] blocked before the model saw it", flush=True)
            if args.show_assessments and verdict.reasons:
                for reason in verdict.reasons:
                    print(f"            {reason}")
            print(f"bot> {verdict.message}\n")
            continue
        if verdict.reasons:  # guardrail errored and failed open
            print(f"\n[guardrail] {verdict.reasons[0]}", file=sys.stderr)

        print("bot> ", end="", flush=True)
        chat.invoke(rt, config, session_id, user_text, verbose=args.verbose)
        print()

    if blocked:
        print(f"\n{blocked} message(s) blocked before reaching the model.")


if __name__ == "__main__":
    main()
