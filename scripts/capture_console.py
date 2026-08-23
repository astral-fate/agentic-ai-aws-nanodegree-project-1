#!/usr/bin/env python3
"""Screenshot the AWS console pages the rubric asks for.

    python scripts/capture_console.py --out evidence/run-01/screenshots

These are **real console screenshots**, taken by driving your installed
Chrome. Nothing here renders a console-lookalike page from API data — a
fabricated image passed off as a console screenshot is the kind of thing that
gets a submission rejected, so the browser really does load the console.

Signing in
----------
The AWS console needs an interactive login. Two ways to get one:

* **Persistent profile (default).** The first run opens a visible Chrome
  window at the sign-in page and waits for you to log in. The session is
  saved to ``.aws-console-profile/`` (git-ignored), so every later run is
  fully automatic and can be headless. You log in once, not once per run.

* **Federated sign-in** (``--signin-url``). ``sts:GetFederationToken``
  produces a URL that logs a browser in without typing anything, so the whole
  thing is headless from the first run. Root credentials cannot call
  GetFederationToken, so this needs an IAM user — see capture-evidence.ps1,
  which mints the URL for you.

Targets come from ``agentcore_config.json`` and ``eval_job.json`` when they
are present, so the deep links point at your actual job, table and function.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

SIGNIN_HOSTS = ("signin.aws.amazon.com", "signin.aws.com")


def console(region: str, path: str) -> str:
    return f"https://{region}.console.aws.amazon.com/{path}"


def build_targets(region: str, cfg: dict, job: dict) -> list[dict]:
    """The four screenshots the rubric names, plus useful supporting ones."""
    table = cfg.get("table_name", "bug-report-tool-stack-bug-reports")
    fn = "bug-report-tool-stack-create-bug-report"
    log_group = quote(f"/aws/lambda/{fn}", safe="").replace("%", "$25")

    targets = [
        {
            "name": "01-bedrock-evaluations",
            # The route is "#evaluation" - no slash, singular. "#/evaluations"
            # renders literally nothing, which is how the first attempt
            # produced a blank page under a correct-looking header.
            "url": console(region, f"bedrock/home?region={region}#evaluation"),
            "note": "Bedrock → Evaluations.",
            "wait": 15000,
            # This view took about a minute to paint in testing, so wait for
            # the job name rather than guessing a sleep.
            "expect": "support-chatbot-eval",
            "attempts": 16,
            "warm_url": console(region, f"bedrock/home?region={region}"),
        },
        {
            "name": "02-dynamodb-bug-reports",
            "url": console(region,
                           f"dynamodbv2/home?region={region}"
                           f"#item-explorer?table={table}"),
            "note": f"DynamoDB → {table} → Explore items.",
            "wait": 10000,
            "expect": "ticketId",
            "attempts": 12,
        },
        {
            "name": "03-lambda-create-bug-report",
            # The Test tab needs a click to show a result, which is not
            # something this can do honestly. The Code tab proves the
            # function and its handler; the CloudWatch target below carries
            # the actual invocation evidence.
            "url": console(region,
                           f"lambda/home?region={region}#/functions/{fn}?tab=code"),
            "note": "Lambda → the create_bug_report function.",
            "wait": 12000,
            "expect": "Code source",
            "attempts": 12,
            "warm_url": console(region, f"lambda/home?region={region}#/functions"),
        },
        {
            "name": "04-lambda-cloudwatch-logs",
            "url": console(region,
                           f"cloudwatch/home?region={region}"
                           f"#logsV2:log-groups/log-group/{log_group}"),
            "note": "CloudWatch log group for the Lambda — the real "
                    "invocations, which is stronger evidence than a console "
                    "test click.",
            "wait": 12000,
            # "Log streams" is not the wording this view uses; match the log
            # group name itself, which is unambiguous.
            "expect": "create-bug-report",
            "attempts": 14,
            "warm_url": console(region,
                                f"cloudwatch/home?region={region}#logsV2:log-groups"),
        },
        {
            "name": "05-cloudformation-stacks",
            "url": console(region, f"cloudformation/home?region={region}#/stacks"),
            "note": "Both stacks, CREATE_COMPLETE.",
            "wait": 8000,
            "expect": "bug-report-tool-stack",
            "attempts": 10,
        },
    ]

    if cfg.get("flow_id"):
        # The Flow canvas - the diagram the rubric asks for. Built by
        # setup_flow.py; the console renders the node graph.
        targets.insert(0, {
            "name": "00-bedrock-flow-diagram",
            "url": console(region,
                           f"bedrock/home?region={region}#/flows/{cfg['flow_id']}"),
            "note": "Bedrock Flows console — the flow diagram, showing the "
                    "classifier, the Condition node and three paths each "
                    "ending at its own Output node.",
            "wait": 15000,
            "expect": "RouteByCategory",
            "attempts": 16,
            "warm_url": console(region, f"bedrock/home?region={region}#/flows"),
        })

    if job.get("jobName"):
        # The evaluations console keys off the job ARN. Included as a best
        # effort: if the fragment shape changes, the list page above still
        # gives you a screenshot to work from.
        # The report route, found by clicking through from the list:
        #   #/eval/model-evaluation/report?job=<jobName>
        # It is keyed by job NAME, not ARN. This is the page carrying the
        # correctness score, so it is the single most important screenshot.
        targets.insert(1, {
            "name": "01b-evaluation-job-results",
            "url": console(region,
                           f"bedrock/home?region={region}"
                           f"#/eval/model-evaluation/report?job={job['jobName']}"),
            "note": f"Evaluation report for {job['jobName']} — the "
                    "correctness score and per-prompt breakdown.",
            "wait": 15000,
            "expect": "Correctness",
            "attempts": 16,
            "warm_url": console(region, f"bedrock/home?region={region}#evaluation"),
        })
    return targets


def is_signin(page) -> bool:
    return any(h in page.url for h in SIGNIN_HOSTS)


# The AWS console shell (nav bar, search, footer) renders immediately and
# contributes roughly this much text. Anything at or below it means the page
# body itself has not painted yet — a screenshot taken then is a blank frame
# under a correct-looking header, which is worse than an obvious failure
# because it looks plausible.
SHELL_TEXT_CHARS = 700


def body_text_length(page) -> int:
    try:
        return page.evaluate("() => (document.body?.innerText || '').length")
    except Exception:  # noqa: BLE001 - page may be mid-navigation
        return 0


def settle(page, initial_wait: int, attempts: int = 4, expect: str = "") -> int:
    """Wait for the console SPA to actually paint something.

    These are single-page apps behind a fragment router: DOMContentLoaded
    fires long before any content exists. Poll the rendered text instead of
    trusting a fixed sleep.
    """
    page.wait_for_timeout(initial_wait)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except PWTimeout:
        pass  # some console pages poll forever and never go idle

    def ready() -> tuple[int, bool]:
        try:
            text = page.evaluate("() => document.body?.innerText || ''")
        except Exception:  # noqa: BLE001
            return 0, False
        enough = len(text) > SHELL_TEXT_CHARS
        if expect:
            enough = enough and expect in text
        return len(text), enough

    length, done = ready()
    for _ in range(attempts):
        if done:
            return length
        page.wait_for_timeout(5000)
        length, done = ready()
    return length if done else min(length, SHELL_TEXT_CHARS)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="evidence/screenshots",
                   help="Directory to write the PNGs into.")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--profile", default=".aws-console-profile",
                   help="Chrome profile directory that keeps you signed in.")
    p.add_argument("--config", default="project/starter/agentcore_config.json")
    p.add_argument("--job", default="project/starter/eval_job.json")
    p.add_argument("--signin-url", default=None,
                   help="Federated sign-in URL (see capture-evidence.ps1). "
                        "Makes the run headless from the very first time.")
    p.add_argument("--headless", action="store_true",
                   help="Force headless. Fails if the profile is not signed in.")
    p.add_argument("--login-timeout", type=int, default=300,
                   help="Seconds to wait for a manual sign-in on first run.")
    args = p.parse_args()

    cfg = {}
    if Path(args.config).exists():
        cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    job = {}
    if Path(args.job).exists():
        job = json.loads(Path(args.job).read_text(encoding="utf-8"))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    profile = Path(args.profile)
    profile.mkdir(parents=True, exist_ok=True)

    targets = build_targets(args.region, cfg, job)
    headless = args.headless or bool(args.signin_url)

    print(f"Capturing {len(targets)} pages into {out}/")
    print(f"  profile : {profile}")
    print(f"  mode    : {'headless' if headless else 'visible window'}")

    captured, failed, blank = [], [], []

    with sync_playwright() as pw:
        try:
            ctx = pw.chromium.launch_persistent_context(
                str(profile.resolve()),
                channel="chrome",           # use installed Chrome, no download
                headless=headless,
                viewport={"width": 1600, "height": 1000},
                args=["--disable-blink-features=AutomationControlled"],
            )
        except Exception as exc:  # noqa: BLE001
            print(f"\nCould not start Chrome: {exc}", file=sys.stderr)
            print("Install Google Chrome, or run: python -m playwright install chromium",
                  file=sys.stderr)
            return 1

        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # --- sign in -------------------------------------------------------
        if args.signin_url:
            print("\nSigning in with the federated URL...")
            page.goto(args.signin_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(5000)
        else:
            page.goto(console(args.region, f"console/home?region={args.region}"),
                      wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(4000)
            if is_signin(page):
                if headless:
                    print("\nNot signed in, and --headless was requested.\n"
                          "Run once without --headless to sign in, or pass "
                          "--signin-url.", file=sys.stderr)
                    ctx.close()
                    return 2
                print("\n" + "=" * 62)
                print("  Sign in to AWS in the Chrome window that just opened.")
                print("  This happens ONCE - the session is saved to the")
                print(f"  profile at {profile}, so later runs are automatic.")
                print(f"  Waiting up to {args.login_timeout}s...")
                print("=" * 62)
                try:
                    page.wait_for_url(
                        lambda url: not any(h in url for h in SIGNIN_HOSTS),
                        timeout=args.login_timeout * 1000,
                    )
                    page.wait_for_timeout(5000)
                    print("  signed in")
                except PWTimeout:
                    print("\nTimed out waiting for sign-in.", file=sys.stderr)
                    ctx.close()
                    return 2

        # --- capture -------------------------------------------------------
        for t in targets:
            name = t["name"]
            print(f"\n  {name}")
            try:
                # Some console sections have moved between fragment routes.
                # Try each candidate and keep the first that actually paints.
                urls = [t["url"], *t.get("alt_urls", [])]
                length = 0
                if t.get("warm_url"):
                    # Prime the service bundle before the fragment route.
                    page.goto(t["warm_url"], wait_until="commit", timeout=90000)
                    settle(page, 8000, attempts=6)

                for i, url in enumerate(urls):
                    page.goto(url, wait_until="commit", timeout=90000)
                    if is_signin(page):
                        raise RuntimeError("bounced to the sign-in page")
                    length = settle(page, t.get("wait", 6000),
                                    attempts=t.get("attempts", 4),
                                    expect=t.get("expect", ""))
                    if length > SHELL_TEXT_CHARS:
                        break
                    if i + 1 < len(urls):
                        print(f"    blank ({length} chars) - trying the next route")

                path = out / f"{name}.png"
                page.screenshot(path=str(path), full_page=True)
                size = path.stat().st_size

                if length <= SHELL_TEXT_CHARS:
                    # Say so rather than filing a blank frame as evidence.
                    print(f"    BLANK: only {length} chars rendered "
                          f"({size:,} bytes) - not usable as evidence")
                    blank.append(name)
                else:
                    print(f"    saved {path} ({size:,} bytes, {length} chars)")
                    captured.append({"name": name, "file": path.name,
                                     "url": page.url, "note": t["note"]})
            except Exception as exc:  # noqa: BLE001
                level = "optional" if t.get("optional") else "FAILED"
                print(f"    {level}: {exc}")
                if not t.get("optional"):
                    failed.append(name)

        ctx.close()

    # --- index -------------------------------------------------------------
    if captured:
        lines = ["# Console screenshots", "",
                 "Captured with `scripts/capture_console.py`, which drives a real",
                 "Chrome session against the AWS console.", "",
                 "| File | Shows | Console location |", "|---|---|---|"]
        for c in captured:
            lines.append(f"| `{c['file']}` | {c['note']} | `{c['url']}` |")
        (out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n  wrote {out / 'README.md'}")

    print(f"\n{len(captured)} captured, {len(failed)} failed")
    if failed:
        print("failed: " + ", ".join(failed), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
