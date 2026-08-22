#!/usr/bin/env python3
"""Turn off the harness's cross-session memory.

    python disable_memory.py

Why this exists
---------------
An AgentCore harness is created with managed long-term memory enabled by
default. That is memory *across* sessions, which is a different thing from
the session state that makes multi-turn bug collection work: session state is
keyed by ``runtimeSessionId`` and is what lets the assistant remember what the
customer said two turns ago. Long-term memory persists after the session ends.

For this project the second one is actively wrong, and it produced a confusing
failure. On a fresh session the assistant was asked to report a checkout bug
and replied:

    A bug report for the checkout page crash has already been filed with
    ticket ID a09a2c6f-...

It had not filed anything in that conversation. It was recalling a ticket from
an earlier run, and because the prompt correctly says "never call the tool
twice for the same problem", it declined to file the new one. Every test then
became dependent on whatever had run before it — which also breaks the
promise in ``generate-eval-dataset.py`` that each case runs in a fresh,
independent session.

``UpdateHarness`` requires only ``harnessId``, so this sends nothing but the
memory setting and leaves the prompt, model and role untouched.

Run it once after ``create_harness.py``. It is idempotent.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import boto3


def wait_ready(acc, harness_id, timeout=300):
    deadline = time.time() + timeout
    status = "UNKNOWN"
    while time.time() < deadline:
        status = acc.get_harness(harnessId=harness_id)["harness"]["status"]
        if status == "READY":
            return status
        if status in ("FAILED", "DELETING"):
            sys.exit(f"Harness entered status {status}.")
        print(f"  status: {status} — waiting...")
        time.sleep(10)
    sys.exit(f"Timed out waiting for the harness (last status: {status}).")


def describe(memory) -> str:
    if not memory:
        return "default (managed long-term memory enabled)"
    if "disabled" in memory:
        return "disabled"
    for key in ("managedMemoryConfiguration", "agentCoreMemoryConfiguration"):
        if key in memory:
            return key
    return json.dumps(memory)


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default="agentcore_config.json")
    p.add_argument("--enable", action="store_true",
                   help="Re-enable managed memory instead of disabling it.")
    args = p.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        sys.exit(f"{args.config} not found — run create_harness.py first.")
    config = json.loads(config_path.read_text(encoding="utf-8"))
    harness_id = config.get("harness_id")
    if not harness_id:
        sys.exit("No harness in the config — run create_harness.py first.")

    acc = boto3.client("bedrock-agentcore-control", region_name=config["region"])

    before = acc.get_harness(harnessId=harness_id)["harness"].get("memory")
    print(f"Current memory setting: {describe(before)}")

    if args.enable:
        memory = {"managedMemoryConfiguration": {}}
        wanted = "managedMemoryConfiguration"
    else:
        memory = {"disabled": {}}
        wanted = "disabled"

    if describe(before) == wanted:
        print("Already set — nothing to do.")
        return

    print(f"Setting memory to: {wanted}")
    # UpdateHarness takes UpdatedHarnessMemoryConfiguration, which wraps the
    # value in `optionalValue` so the field can be cleared as well as set.
    # CreateHarness takes the inner shape directly - passing the CreateHarness
    # form here fails with:
    #   Unknown parameter in memory: "disabled", must be one of: optionalValue
    acc.update_harness(harnessId=harness_id, memory={"optionalValue": memory})
    wait_ready(acc, harness_id)

    after = acc.get_harness(harnessId=harness_id)["harness"].get("memory")
    print(f"Memory setting is now: {describe(after)}")

    config["memory"] = wanted
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Recorded in {args.config}.")
    if wanted == "disabled":
        print("\nSessions are still stateful within a conversation — only "
              "recall across separate sessions is off.")


if __name__ == "__main__":
    main()
