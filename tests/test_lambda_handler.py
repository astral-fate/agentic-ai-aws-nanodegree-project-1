"""The create_bug_report Lambda, exercised against a fake DynamoDB table.

This is the real handler from ``project/starter/create_bug_report.py`` - only
the table is faked - so these assertions cover the code that actually runs in
AWS.
"""

from __future__ import annotations

import uuid

import pytest

from fake_agentcore import FakeLambdaContext

GOOD_EVENT = {
    "description": "The checkout page crashes when I click the Pay button",
    "stepsToReproduce": "1. Add an item to the cart. 2. Go to checkout. 3. Click Pay.",
    "environment": "Chrome 120 on macOS Sonoma",
}


def test_files_a_ticket_and_returns_an_open_status(lambda_module, fake_table):
    result = lambda_module.lambda_handler(dict(GOOD_EVENT), FakeLambdaContext())

    assert result["status"] == "OPEN"
    uuid.UUID(result["ticketId"])  # raises if it is not a real UUID
    assert len(fake_table.items) == 1


def test_stored_item_matches_what_the_customer_said(lambda_module, fake_table):
    result = lambda_module.lambda_handler(dict(GOOD_EVENT), FakeLambdaContext())
    item = fake_table.items[0]

    assert item["ticketId"] == result["ticketId"]
    assert item["description"] == GOOD_EVENT["description"]
    assert item["stepsToReproduce"] == GOOD_EVENT["stepsToReproduce"]
    assert item["environment"] == GOOD_EVENT["environment"]
    assert item["status"] == "OPEN"
    assert item["createdAt"].endswith("+00:00")


@pytest.mark.parametrize(
    "field", ["description", "stepsToReproduce", "environment"]
)
def test_a_missing_field_is_rejected_without_writing(
    lambda_module, fake_table, field
):
    event = dict(GOOD_EVENT)
    del event[field]

    result = lambda_module.lambda_handler(event, FakeLambdaContext())

    assert field in result["error"]
    assert fake_table.items == []


@pytest.mark.parametrize("blank", ["", "   ", "\n\t"])
def test_a_blank_field_is_rejected_without_writing(
    lambda_module, fake_table, blank
):
    """The model sometimes fills a required field with whitespace to satisfy
    the schema. That must not become a ticket."""
    event = dict(GOOD_EVENT, environment=blank)

    result = lambda_module.lambda_handler(event, FakeLambdaContext())

    assert "environment" in result["error"]
    assert fake_table.items == []


def test_error_message_tells_the_model_to_go_back_and_ask(lambda_module):
    result = lambda_module.lambda_handler({"description": "x"}, FakeLambdaContext())

    assert "Ask the customer" in result["error"]
    assert "stepsToReproduce" in result["error"]
    assert "environment" in result["error"]


def test_all_three_missing_fields_are_reported_at_once(lambda_module):
    result = lambda_module.lambda_handler({}, FakeLambdaContext())

    for field in ("description", "stepsToReproduce", "environment"):
        assert field in result["error"]


def test_namespaced_tool_name_is_accepted(lambda_module, fake_table):
    """The gateway sends '<targetName>___<toolName>' - three underscores."""
    ctx = FakeLambdaContext("bugreports___create_bug_report")

    result = lambda_module.lambda_handler(dict(GOOD_EVENT), ctx)

    assert result["status"] == "OPEN"
    assert len(fake_table.items) == 1


def test_an_unexpected_tool_name_is_refused(lambda_module, fake_table):
    ctx = FakeLambdaContext("bugreports___delete_everything")

    result = lambda_module.lambda_handler(dict(GOOD_EVENT), ctx)

    assert "unsupported tool" in result["error"]
    assert fake_table.items == []


def test_missing_client_context_still_works(lambda_module, fake_table):
    """Direct console test invokes have no client context at all."""

    class Bare:
        pass

    result = lambda_module.lambda_handler(dict(GOOD_EVENT), Bare())

    assert result["status"] == "OPEN"
    assert len(fake_table.items) == 1


def test_a_non_dict_event_is_refused(lambda_module, fake_table):
    result = lambda_module.lambda_handler(["not", "a", "dict"], FakeLambdaContext())

    assert "unexpected event shape" in result["error"]
    assert fake_table.items == []


def test_every_ticket_id_is_unique(lambda_module, fake_table):
    ids = {
        lambda_module.lambda_handler(dict(GOOD_EVENT), FakeLambdaContext())["ticketId"]
        for _ in range(25)
    }

    assert len(ids) == 25
    assert len(fake_table.items) == 25


def test_the_console_test_event_from_the_instructions_works(
    lambda_module, fake_table
):
    """The exact payload the project instructions tell you to paste into the
    Lambda console Test tab."""
    event = {
        "description": "The checkout page crashes when I click the Pay button",
        "stepsToReproduce": "1. Add an item to the cart. 2. Go to checkout. 3. Click Pay.",
        "environment": "Chrome 120 on macOS Sonoma",
    }

    result = lambda_module.lambda_handler(event, FakeLambdaContext())

    assert set(result) == {"ticketId", "status"}
    assert result["status"] == "OPEN"
