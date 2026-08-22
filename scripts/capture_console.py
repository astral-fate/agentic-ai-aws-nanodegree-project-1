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
            "url": console(region, f"bedrock/home?region={region}#/evaluations"),
            "note": "Bedrock → Evaluations. Open your job from this list; the "
                    "job page itself needs one click.",
            "wait": 6000,
        },
        {
            "name": "02-dynamodb-bug-reports",
            "url": console(region,
                           f"dynamodbv2/home?region={region}"
                           f"#item-explorer?table={table}"),
            "note": f"DynamoDB → {table} → Explore items.",
            "wait": 8000,
        },
        {
            "name": "03-lambda-create-bug-report",
            "url": console(region,
                           f"lambda/home?region={region}#/functions/{fn}?tab=testing"),
            "note": "Lambda → the create_bug_report function → Test tab.",
            "wait": 8000,
        },
        {
            "name": "04-lambda-cloudwatch-logs",
            "url": console(region,
                           f"cloudwatch/home?region={region}"
                           f"#logsV2:log-groups/log-group/{log_group}"),
            "note": "CloudWatch log group for the Lambda — shows the real "
                    "events the gateway delivered.",
            "wait": 8000,
        },
        {
            "name": "05-cloudformation-stacks",
            "url": console(region, f"cloudformation/home?region={region}#/stacks"),
            "note": "Both stacks, CREATE_COMPLETE.",
            "wait": 6000,
        },
    ]

    if job.get("jobArn"):
        # The evaluations console keys off the job ARN. Included as a best
        # effort: if the fragment shape changes, the list page above still
        # gives you a screenshot to work from.
        targets.insert(1, {
            "name": "01b-bedrock-evaluation-job",
            "url": console(region,
                           f"bedrock/home?region={region}"
                           f"#/evaluations/{quote(job['jobArn'], safe='')}"),
            "note": f"Results page for {job.get('jobName', 'the job')}.",
            "wait": 8000,
            "optional": True,
        })
    return targets


def is_signin(page) -> bool:
    return any(h in page.url for h in SIGNIN_HOSTS)


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

    captured, failed = [], []

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
                page.goto(t["url"], wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(t.get("wait", 6000))

                if is_signin(page):
                    raise RuntimeError("bounced to the sign-in page")

                path = out / f"{name}.png"
                page.screenshot(path=str(path), full_page=True)
                size = path.stat().st_size
                print(f"    saved {path} ({size:,} bytes)")
                captured.append({"name": name, "file": path.name,
                                 "url": t["url"], "note": t["note"]})
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
