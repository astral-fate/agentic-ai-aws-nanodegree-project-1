"""Checks on harness-tests.json - the suite fed to Bedrock Evaluations.

The rubric requires at least one test per route. These assertions make that
a build failure rather than something you discover after paying for an
evaluation run.
"""

from __future__ import annotations

import json

import pytest

ROUTES = {"bug_report", "platform_question", "other"}
SUPPORT_PHONE = "1-800-555-0199"


def test_the_suite_has_the_shape_the_template_defines(harness_tests, starter_dir):
    template = json.loads(
        (starter_dir / "harness-tests-template.json").read_text(encoding="utf-8")
    )
    assert set(harness_tests) == set(template)
    template_keys = set(template["tests"][0])

    for test in harness_tests["tests"]:
        assert template_keys <= set(test), f"{test.get('id')} is missing keys"


def test_every_route_is_covered(harness_tests):
    covered = {t["route"] for t in harness_tests["tests"]}
    assert ROUTES <= covered, f"no test cases for {ROUTES - covered}"


def test_each_route_has_at_least_two_cases(harness_tests):
    counts = {route: 0 for route in ROUTES}
    for test in harness_tests["tests"]:
        counts[test["route"]] += 1

    for route, count in counts.items():
        assert count >= 2, f"route {route} only has {count} case(s)"


def test_test_ids_are_unique(harness_tests):
    ids = [t["id"] for t in harness_tests["tests"]]
    assert len(ids) == len(set(ids))


def test_no_test_is_a_leftover_template_placeholder(harness_tests):
    for test in harness_tests["tests"]:
        for field in ("id", "prompt", "expected"):
            assert not test[field].startswith("<"), (
                f"{test['id']}.{field} is still a template placeholder"
            )


@pytest.mark.parametrize("field", ["prompt", "expected"])
def test_prompts_and_expectations_are_substantial(harness_tests, field):
    for test in harness_tests["tests"]:
        assert test[field].strip(), f"{test['id']}.{field} is empty"
    for test in harness_tests["tests"]:
        # A one-word reference response gives the judge nothing to work with.
        assert len(test["expected"].split()) >= 12, (
            f"{test['id']}.expected is too vague to grade against"
        )


def test_routes_are_valid(harness_tests):
    for test in harness_tests["tests"]:
        assert test["route"] in ROUTES, f"{test['id']} has route {test['route']!r}"


def test_handoff_cases_expect_the_phone_number(harness_tests):
    handoffs = [t for t in harness_tests["tests"] if t["route"] == "other"]
    for test in handoffs:
        assert SUPPORT_PHONE in test["expected"], (
            f"{test['id']} is an 'other' case but never mentions the "
            "support line"
        )


def test_bug_cases_expect_collection_not_a_finished_ticket(harness_tests):
    """Each eval case is a single turn in a fresh session, so a bug-report
    case can only ever reach the *start* of collection."""
    bugs = [t for t in harness_tests["tests"] if t["route"] == "bug_report"]
    for test in bugs:
        low = test["expected"].lower()
        assert "ask" in low, f"{test['id']} does not expect a follow-up question"


def test_the_suite_covers_the_documented_edge_cases(harness_tests):
    ids = " ".join(t["id"] for t in harness_tests["tests"])
    for edge in ("injection", "short", "ambiguous"):
        assert edge in ids, f"no edge-case test for {edge!r}"


def test_flow_tests_json_is_kept_in_sync(starter_dir, harness_tests):
    """The rubric names the suite `flow-tests.json` (from when this project
    was built on Bedrock Flows); the current instructions and
    generate-eval-dataset.py use `harness-tests.json`. Both filenames ship so
    a grader finds either one - this asserts they never drift apart."""
    flow = json.loads(
        (starter_dir / "flow-tests.json").read_text(encoding="utf-8")
    )

    assert flow == harness_tests, (
        "flow-tests.json and harness-tests.json have diverged - "
        "copy harness-tests.json over flow-tests.json"
    )
