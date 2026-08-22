#!/usr/bin/env python3
"""Copy the deliverables from project/starter into run-all.sh's heredocs.

run-all.sh inlines `system_prompt.txt` and `harness-tests.json` so it can be
pasted into CloudShell as one self-contained command. That duplication has to
be kept honest: editing the prompt in `project/starter` without re-inlining it
would make the CloudShell run silently deploy the old prompt.

`regenerate-paste.sh` calls this first, so the normal workflow is:

    edit project/starter/system_prompt.txt
    bash cloudshell/regenerate-paste.sh
    python -m pytest

The test suite asserts the heredocs match, so a forgotten sync is a failure
rather than a surprise at deploy time.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
STARTER = REPO / "project" / "starter"
SCRIPT = HERE / "run-all.sh"

# heredoc delimiter -> source file
INLINED = {
    "PROMPT_EOF": STARTER / "system_prompt.txt",
    "TESTS_EOF": STARTER / "harness-tests.json",
}


def main() -> int:
    script = SCRIPT.read_text(encoding="utf-8", newline="\n")
    changed = []

    for delim, source in INLINED.items():
        pattern = re.compile(rf"(<<'{delim}'\n)(.*?)(\n{delim}\n)", re.S)
        match = pattern.search(script)
        if not match:
            print(f"error: no {delim} heredoc in {SCRIPT.name}", file=sys.stderr)
            return 1

        wanted = source.read_text(encoding="utf-8").replace("\r\n", "\n")
        # The heredoc body excludes the trailing newline before the delimiter.
        body = wanted[:-1] if wanted.endswith("\n") else wanted

        if match.group(2) == body:
            continue

        script = (
            script[: match.start()]
            + match.group(1) + body + match.group(3)
            + script[match.end():]
        )
        changed.append(source.name)

    if changed:
        SCRIPT.write_text(script, encoding="utf-8", newline="\n")
        print(f"re-inlined: {', '.join(changed)}")
    else:
        print("inlined copies already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
