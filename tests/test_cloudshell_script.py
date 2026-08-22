"""Checks on cloudshell/run-all.sh.

The script inlines the project deliverables so it can be pasted into AWS
CloudShell as a single self-contained command. That duplication is the point,
but it can drift: edit `system_prompt.txt` in the repo and the CloudShell run
would silently deploy the old prompt. These tests make that a build failure.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess

import pytest

SCRIPT_REL = "cloudshell/run-all.sh"


@pytest.fixture(scope="module")
def script(request) -> str:
    path = request.config.rootpath / SCRIPT_REL
    assert path.exists(), f"{SCRIPT_REL} is missing"
    return path.read_text(encoding="utf-8")


def _heredoc(script: str, delim: str) -> str | None:
    """Pull the body of a quoted heredoc out of the script."""
    match = re.search(rf"<<'{delim}'\n(.*?)\n{delim}\n", script, re.S)
    return match.group(1) + "\n" if match else None


def test_the_inlined_system_prompt_matches_the_repo(script, starter_dir):
    inlined = _heredoc(script, "PROMPT_EOF")

    assert inlined is not None, "PROMPT_EOF heredoc not found"
    assert inlined == (starter_dir / "system_prompt.txt").read_text(encoding="utf-8"), (
        "cloudshell/run-all.sh would deploy a different system prompt than the "
        "one in project/starter - re-copy it into the PROMPT_EOF heredoc"
    )


def test_the_inlined_test_suite_matches_the_repo(script, harness_tests):
    inlined = _heredoc(script, "TESTS_EOF")

    assert inlined is not None, "TESTS_EOF heredoc not found"
    assert json.loads(inlined) == harness_tests, (
        "cloudshell/run-all.sh would run a different test suite than "
        "harness-tests.json"
    )


def _working_bash() -> str | None:
    """A bash that actually runs.

    On Windows ``shutil.which("bash")`` often finds the WSL stub, which fails
    with an exec error if no distro is installed. Probe before trusting it,
    and fall back to Git Bash.
    """
    candidates = [
        shutil.which("bash"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    ]
    for candidate in candidates:
        if not candidate:
            continue
        try:
            probe = subprocess.run(
                [candidate, "-c", "exit 0"], capture_output=True, timeout=20
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if probe.returncode == 0:
            return candidate
    return None


def test_the_script_is_valid_bash(request):
    bash = _working_bash()
    if bash is None:
        pytest.skip("no working bash on this machine")
    path = request.config.rootpath / SCRIPT_REL

    result = subprocess.run(
        [bash, "-n", str(path)], capture_output=True, text=True
    )

    assert result.returncode == 0, result.stderr


def test_it_pins_the_region_and_model_the_course_requires(script):
    assert 'REGION="${REGION:-us-east-1}"' in script
    assert "us.amazon.nova-pro-v1:0" in script


def test_it_checks_nova_access_before_deploying_anything(script):
    """Model access is the most common blocker. Failing fast on it saves
    several minutes of CloudFormation before the real error appears."""
    nova_check = script.index("bedrock-runtime converse")
    first_deploy = script.index("cloudformation deploy")

    assert nova_check < first_deploy, "the Nova access check must come first"


def test_it_never_destroys_working_resources(script):
    """Teardown is printed for the user to run, not executed - the evidence
    has to survive the run.

    The one exception is a stack stuck in ROLLBACK_COMPLETE or CREATE_FAILED:
    CloudFormation cannot update those, so they have to be deleted before a
    redeploy. That is checked separately below.
    """
    body = script.split("Tear down when you are done")[0]

    for destructive in ("s3 rm", "cleanup_agentcore.py", "delete_harness"):
        assert destructive not in body, (
            f"{destructive!r} runs during the script; it should only appear in "
            "the teardown instructions printed at the end"
        )


def test_stack_deletion_only_happens_to_recover_a_failed_stack(script):
    """Every delete-stack in the body must sit in a branch guarded by a failed
    stack status - never on a healthy stack."""
    body = script.split("Tear down when you are done")[0]

    for match in re.finditer(r"^.*delete-stack.*$", body, re.M):
        preceding = body[: match.start()]
        # The nearest case-branch label above this line.
        guards = re.findall(r"^\s*([A-Z_|]*(?:ROLLBACK_COMPLETE|CREATE_FAILED)[A-Z_|]*)\)",
                            preceding, re.M)
        assert guards, (
            f"unguarded stack deletion: {match.group(0).strip()!r}"
        )


def test_a_recovered_stack_is_waited_on_before_redeploy(script):
    """Deleting a stack is asynchronous - redeploying before it finishes fails
    with AlreadyExistsException."""
    assert script.count("wait stack-delete-complete") >= 2


def test_it_is_resumable(script):
    """CloudShell sessions drop. Re-running must not duplicate resources."""
    assert "cfn_status" in script
    assert 'cfg_get gateway_id' in script
    assert "already deployed" in script


def test_it_writes_both_test_suite_filenames(script):
    """The rubric says flow-tests.json, the instructions say
    harness-tests.json."""
    assert "cp harness-tests.json flow-tests.json" in script


# --- the self-extracting paste ---------------------------------------------
#
# PASTE-THIS.txt is generated by cloudshell/regenerate-paste.sh. It carries the
# gzipped script as base64 inside a quoted heredoc, wrapped at 76 columns, and
# verifies a sha256 after decoding.
#
# An earlier version was a single 20KB `echo <blob> | base64 -d` line. It got
# truncated on paste into CloudShell and surfaced as "gunzip: invalid
# compressed data - format violated", with no clue what had gone wrong. Hence
# both the wrapping and the checksum.


import base64
import gzip
import hashlib

PASTE_REL = "cloudshell/PASTE-THIS.txt"


def _payload(paste: str) -> bytes:
    """The decoded script the paste would write."""
    match = re.search(r"<<'B64_EOF'\n(.*?)\nB64_EOF\n", paste, re.S)
    assert match, "PASTE-THIS.txt has no B64_EOF heredoc"
    return gzip.decompress(base64.b64decode(match.group(1)))


@pytest.fixture(scope="module")
def paste(request) -> str:
    return (request.config.rootpath / PASTE_REL).read_text(encoding="utf-8")


def test_the_paste_decodes_to_the_script(request, paste):
    script = (request.config.rootpath / SCRIPT_REL).read_bytes()

    assert _payload(paste) == script, (
        "PASTE-THIS.txt is stale - run cloudshell/regenerate-paste.sh"
    )


def test_the_embedded_checksum_matches_the_script(request, paste):
    """The paste verifies this hash after decoding; a stale hash would make
    every correct paste report itself as corrupted."""
    script = (request.config.rootpath / SCRIPT_REL).read_bytes()
    expected = hashlib.sha256(script).hexdigest()

    assert expected in paste, (
        "the sha256 baked into PASTE-THIS.txt does not match run-all.sh - "
        "run cloudshell/regenerate-paste.sh"
    )


def test_no_line_is_long_enough_to_be_mangled_on_paste(paste):
    """The bug that broke the first version was a single ~20,000 character
    line, which terminal paste truncated. Ordinary shell-length lines are
    fine; the payload itself must stay wrapped."""
    lines = paste.splitlines()
    longest = max(len(line) for line in lines)

    assert longest <= 200, f"longest line is {longest} chars; wrap the base64"

    # The base64 body specifically - the only part big enough to matter.
    body = re.search(r"<<'B64_EOF'\n(.*?)\nB64_EOF\n", paste, re.S).group(1)
    widest = max(len(line) for line in body.splitlines())

    assert widest <= 80, f"base64 wrapped at {widest} columns; use 76"


def test_a_corrupted_paste_reports_itself_clearly(paste):
    """Rather than leaving the user staring at a gunzip error."""
    assert "PASTE INCOMPLETE OR CORRUPTED" in paste
    assert "Upload file" in paste, "the fallback route must be spelled out"
    assert "sha256sum" in paste


def test_the_base64_survives_word_splitting(paste):
    """It is read from a file by `base64 -d`, never interpolated into an
    unquoted `echo` - that was the other half of the original bug."""
    assert "<<'B64_EOF'" in paste, "the heredoc must be quoted"
    assert "base64 -d /tmp/ra.b64" in paste
    assert not re.search(r"echo \$?[A-Za-z0-9+/=]{100,}", paste), (
        "the payload must not be echoed as a shell word"
    )


def test_the_decoded_paste_has_unix_line_endings(paste):
    decoded = _payload(paste)

    assert b"\r\n" not in decoded, "the paste would write a CRLF script"
    assert decoded.startswith(b"#!/usr/bin/env bash\n")
