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


# --- the reviewer-facing evidence images -----------------------------------
#
# Attempt 2 failed with: "Add the Full Flow Diagram / Show the Classifier
# Prompt / Show the Condition Expressions / Add the Required FAQ Evidence
# Screenshots". Links in a nested folder were not enough - the images have to
# render on the page.


def _embedded(md_rel: str) -> list[tuple[str, str]]:
    import re
    text = (REPO_ROOT / md_rel).read_text(encoding="utf-8")
    return re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", text)


@pytest.mark.parametrize("md_rel", ["README.md", "evidence/README.md"])
def test_every_embedded_image_resolves(md_rel):
    """A broken image path renders as a blank box, which is worse than a link
    because it looks like the evidence is missing."""
    base = (REPO_ROOT / md_rel).parent
    for alt, rel in _embedded(md_rel):
        assert (base / rel).exists(), f"{md_rel} references a missing {rel}"
        assert alt.strip(), f"{md_rel} embeds {rel} with no alt text"


def test_the_four_reviewer_items_are_shown_inline():
    """Not linked - embedded, so they render on the page itself."""
    embedded = " ".join(rel for _, rel in _embedded("evidence/README.md"))

    for name, what in [
        ("06-flow-diagram", "the full flow diagram"),
        ("07-classifier-prompt", "the classifier prompt"),
        ("08-condition-expressions", "the condition expressions"),
        ("09-faq-embedded-in-prompt", "the FAQ evidence"),
        ("10-faq-and-handoff-responses", "the route responses"),
    ]:
        assert name in embedded, f"{what} ({name}) is not embedded inline"


def test_the_landing_page_shows_the_headline_evidence():
    """A reviewer who opens the repo and reads no further should still see
    the flow and the score."""
    embedded = " ".join(rel for _, rel in _embedded("README.md"))

    assert "06-flow-diagram" in embedded
    assert "01b-evaluation-job-results" in embedded


def test_rendered_images_are_not_dressed_up_as_the_console():
    """They present real prompt text and real replies. Styling them to look
    like an AWS console screenshot would make them fabricated records."""
    source = (SCRIPTS / "render_evidence.py").read_text(encoding="utf-8")

    assert "None of them imitate the AWS console" in source
    # Each page must name the file it was rendered from.
    assert "class='src'" in source or 'class="src"' in source


def _links(md_rel: str) -> list[tuple[str, str]]:
    import re
    return re.findall(r"\[([^\]]*)\]\(([^)]+)\)",
                      (REPO_ROOT / md_rel).read_text(encoding="utf-8"))


@pytest.mark.parametrize("md_rel", ["README.md", "evidence/README.md",
                                    "SUBMISSION.md"])
def test_no_broken_relative_links(md_rel):
    """A dead link in the evidence index sends the reviewer to a 404, which
    reads exactly like the artefact is missing."""
    base = (REPO_ROOT / md_rel).parent
    broken = [
        target for _, target in _links(md_rel)
        if not target.startswith(("http://", "https://", "#", "mailto:"))
        and not (base / target).exists()
    ]

    assert not broken, f"{md_rel} links to missing files: {broken}"


def test_every_image_is_clickable(md_rel="evidence/README.md"):
    """Embedded as [![alt](p)](p) so clicking opens it full size - the
    inline render is downscaled and the prompt text is unreadable at that
    size."""
    import re

    text = (REPO_ROOT / md_rel).read_text(encoding="utf-8")
    plain = re.findall(r"(?<!\[)!\[([^\]]*)\]\(([^)]+)\)(?!\])", text)

    assert not plain, f"these images are not wrapped in a link: {plain}"


def test_the_index_table_lists_every_screenshot():
    """One place with every path, so nothing has to be hunted for."""
    text = (REPO_ROOT / "evidence" / "README.md").read_text(encoding="utf-8")
    shots = sorted(
        p.name for p in
        (REPO_ROOT / "evidence" / "run-02" / "screenshots").glob("*.png")
    )

    missing = [s for s in shots if s not in text]
    assert not missing, f"not listed in the index table: {missing}"


# --- the real Bedrock Flow -------------------------------------------------


def test_the_flow_canvas_is_captured_when_a_flow_exists(capture):
    """The rubric asks for a flow diagram. setup_flow.py builds a real Flow,
    and the console renders its node graph - so there is an actual canvas to
    screenshot rather than only a hand-drawn one."""
    cfg = dict(CONFIG, flow_id="FLOW123ABC")
    targets = capture.build_targets("us-east-1", cfg, JOB)
    flow = next((t for t in targets if "#/flows/" in t["url"]), None)

    assert flow is not None, "no flow-canvas target"
    assert "FLOW123ABC" in flow["url"]
    assert flow["expect"] == "RouteByCategory", (
        "should wait for a node name, so a half-rendered canvas is not saved"
    )


def test_no_flow_target_without_a_flow(capture):
    targets = capture.build_targets("us-east-1", CONFIG, JOB)

    assert not any("#/flows/" in t["url"] for t in targets)


def test_the_flow_has_the_shape_the_rubric_describes():
    """Input -> classifier Prompt -> Condition -> three branches, each ending
    at its own Output node."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "setup_flow", REPO_ROOT / "project" / "starter" / "setup_flow.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    d = m.build_definition("FAQ TEXT")
    kinds = {}
    for n in d["nodes"]:
        kinds.setdefault(n["type"], []).append(n["name"])

    assert len(kinds["Input"]) == 1
    assert len(kinds["Condition"]) == 1, "one Condition node drives the routing"
    assert len(kinds["Output"]) == 3, "each path needs its own Output node"
    assert len(kinds["Prompt"]) == 4, "classifier plus one prompt per branch"

    # Every Output is reached from a different branch.
    to_output = {c["source"] for c in d["connections"]
                 if c["target"] in kinds["Output"]}
    assert len(to_output) == 3, "the three paths must be distinct"


def test_the_condition_node_has_real_expressions():
    """The rubric asks for the Condition node expressions specifically."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "setup_flow", REPO_ROOT / "project" / "starter" / "setup_flow.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)

    d = m.build_definition("FAQ TEXT")
    cond = next(n for n in d["nodes"] if n["type"] == "Condition")
    conditions = cond["configuration"]["condition"]["conditions"]

    named = {c["name"]: c.get("expression") for c in conditions}
    assert named["IsBugReport"] == 'category == "BUG_REPORT"'
    assert named["IsPlatformQuestion"] == 'category == "PLATFORM_QUESTION"'
    assert "default" in named, "the else branch must exist"


def test_the_flow_validates_before_it_creates_anything():
    """A bad definition should fail with the API's own message, not leave a
    broken flow behind."""
    src = (REPO_ROOT / "project" / "starter" / "setup_flow.py").read_text(encoding="utf-8")

    assert src.index("validate_flow_definition") < src.index("create_flow")
