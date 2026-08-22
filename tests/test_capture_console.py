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


def test_the_evaluation_job_link_is_optional(capture):
    """The Bedrock console's job-detail fragment is not a documented URL
    shape. If it stops resolving, the run must still produce the other
    screenshots rather than failing outright."""
    targets = capture.build_targets("us-east-1", CONFIG, JOB)
    job_target = next(t for t in targets if "evaluation-job" in t["url"])

    assert job_target.get("optional") is True


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
