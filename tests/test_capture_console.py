"""The console screenshot automation.

`scripts/capture_console.py` drives a real Chrome session against the AWS
console. The tests that matter here are about what it points at, and about
the two things that must never end up in the repo: the browser profile (a
live console session cookie is a credential) and the IAM key used for
federated sign-in.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from conftest import REPO_ROOT, _load_module

SCRIPTS = REPO_ROOT / "scripts"


@pytest.fixture(scope="module")
def capture():
    sys.modules.pop("capture_console", None)
    pytest.importorskip("playwright", reason="playwright is not installed")
    return _load_module(SCRIPTS / "capture_console.py", "capture_console")


CONFIG = {"table_name": "bug-report-tool-stack-bug-reports", "region": "us-east-1"}
JOB = {"jobArn": "arn:aws:bedrock:us-east-1:1234:evaluation-job/abc",
       "jobName": "support-chatbot-eval-1"}


def test_it_covers_the_pages_the_rubric_names(capture):
    targets = capture.build_targets("us-east-1", CONFIG, JOB)
    urls = " ".join(t["url"] for t in targets)

    assert "bedrock/home" in urls, "no Bedrock Evaluations page"
    assert "dynamodbv2/home" in urls, "no DynamoDB page"
    assert "lambda/home" in urls, "no Lambda page"


def test_the_deep_links_use_the_real_resource_names(capture):
    targets = capture.build_targets("us-east-1", CONFIG, JOB)
    urls = " ".join(t["url"] for t in targets)

    assert CONFIG["table_name"] in urls
    assert "bug-report-tool-stack-create-bug-report" in urls


def test_the_bedrock_route_has_no_slash(capture):
    """`#/evaluations` renders literally nothing — the console route is
    `#evaluation`, singular and without a slash. The wrong one produced a
    blank page under a correct-looking AWS header, which is the worst kind of
    failure because it looks like valid evidence."""
    targets = capture.build_targets("us-east-1", CONFIG, JOB)
    bedrock = next(t for t in targets if "bedrock" in t["url"])

    assert bedrock["url"].endswith("#evaluation")
    assert "#/evaluations" not in bedrock["url"]


def test_slow_console_pages_wait_for_their_own_content(capture):
    """A fixed sleep is not enough: the Bedrock evaluations view took about a
    minute to paint. Each slow target names text that only exists once the
    page is really rendered."""
    targets = capture.build_targets("us-east-1", CONFIG, JOB)
    by_name = {t["name"]: t for t in targets}

    assert by_name["01-bedrock-evaluations"]["expect"] == "support-chatbot-eval"
    assert by_name["02-dynamodb-bug-reports"]["expect"] == "ticketId"
    assert by_name["05-cloudformation-stacks"]["expect"] == "bug-report-tool-stack"


def test_heavy_console_bundles_are_warmed_first(capture):
    """On a cold browser profile the Bedrock evaluations view never painted.
    Loading the service root first lets the bundle cache."""
    targets = capture.build_targets("us-east-1", CONFIG, JOB)
    bedrock = next(t for t in targets if "bedrock" in t["url"])

    assert bedrock.get("warm_url"), "no warm-up navigation for Bedrock"


def test_it_works_without_a_config_or_job_file(capture):
    """Falls back to the documented default names."""
    targets = capture.build_targets("us-east-1", {}, {})

    assert targets
    urls = " ".join(t["url"] for t in targets)
    assert "bug-report-tool-stack-bug-reports" in urls
    assert "evaluation-job" not in urls, "no job link without eval_job.json"


def test_every_target_is_an_aws_console_url(capture):
    """The whole point is that these are real console pages. A target
    pointing anywhere else would mean the screenshot is not what it claims."""
    for t in capture.build_targets("us-east-1", CONFIG, JOB):
        assert t["url"].startswith("https://us-east-1.console.aws.amazon.com/"), (
            f"{t['name']} does not point at the AWS console: {t['url']}"
        )


def test_it_never_renders_a_console_lookalike(capture):
    """Guard against the tempting shortcut: building an HTML page that looks
    like the console from API data and screenshotting that. It would be a
    fabricated record."""
    source = (SCRIPTS / "capture_console.py").read_text(encoding="utf-8")

    for forbidden in ("set_content(", "data:text/html", "<html"):
        assert forbidden not in source, (
            f"{forbidden!r} suggests the script renders its own page instead "
            "of screenshotting the real console"
        )


# --- the two things that must stay out of git ------------------------------


@pytest.mark.parametrize(
    "path", [".aws-console-profile/Cookies", ".evidence-capture-key.json"]
)
def test_the_credentials_it_creates_are_git_ignored(path):
    """A live console session cookie and an IAM secret key. Either one in the
    repo would be a credential leak."""
    result = subprocess.run(
        ["git", "check-ignore", "-v", path],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )

    assert result.returncode == 0, f"{path} is NOT git-ignored"


def test_the_powershell_wrapper_exists_and_is_wired_up():
    ps1 = (SCRIPTS / "capture-evidence.ps1").read_text(encoding="utf-8")

    assert "capture_console.py" in ps1, "the wrapper never calls the capturer"
    assert "aws s3 cp" in ps1, "no S3 upload"
    assert "git commit" in ps1, "no commit step"
    assert "GetFederationToken" in ps1 or "get-federation-token" in ps1


def test_the_wrapper_warns_that_root_cannot_federate():
    """Root credentials cannot call GetFederationToken, and the account this
    was run from is root. Failing with a raw AccessDenied would be a poor
    way to discover that."""
    ps1 = (SCRIPTS / "capture-evidence.ps1").read_text(encoding="utf-8")

    assert ":root$" in ps1
    assert "Root cannot call GetFederationToken" in ps1


def test_the_evaluation_report_page_is_a_target(capture):
    """The reviewer asked for the Bedrock Evaluation job RESULTS page. The
    evaluations LIST page is not that page - it shows job names and statuses,
    not the correctness score."""
    targets = capture.build_targets("us-east-1", CONFIG, JOB)
    report = next((t for t in targets if "report" in t["url"]), None)

    assert report is not None, "no evaluation report target"
    assert f"job={JOB['jobName']}" in report["url"], (
        "the report route is keyed by job NAME, not ARN"
    )
    assert report["expect"] == "Correctness", (
        "must wait for the score to render, not just any content"
    )


def test_the_report_route_is_the_one_that_actually_works(capture):
    """Found by clicking through from the list. Guessing produced blanks."""
    targets = capture.build_targets("us-east-1", CONFIG, JOB)
    report = next(t for t in targets if "report" in t["url"])

    assert "#/eval/model-evaluation/report?job=" in report["url"]
