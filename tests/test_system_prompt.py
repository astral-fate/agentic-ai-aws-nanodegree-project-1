"""Structural checks on the project's main deliverable, system_prompt.txt.

These do not judge whether the prompt is *good* - only Bedrock Evaluations
can do that. They catch the mistakes that silently break the project: a lost
``{{FAQ}}`` placeholder, a renamed tool, a route that stopped being
described, or a phone number typo.
"""

from __future__ import annotations

import re

SUPPORT_PHONE = "1-800-555-0199"
TOOL_NAME = "create_bug_report"
TOOL_FIELDS = ("description", "stepsToReproduce", "environment")


def _flat(text: str) -> str:
    """Lowercased, with runs of whitespace collapsed.

    The prompt is hard-wrapped for readability, so a phrase like "single
    source of truth" is split across two lines in the file. Searching the raw
    text for it would fail for no good reason.
    """
    return " ".join(text.split()).lower()


def test_faq_placeholder_appears_exactly_once(system_prompt_text):
    """create_harness.py substitutes this; losing it means the chatbot
    answers platform questions with no FAQ at all."""
    assert system_prompt_text.count("{{FAQ}}") == 1


def test_rendering_leaves_no_placeholder_behind(rendered_prompt):
    assert "{{FAQ}}" not in rendered_prompt
    assert "{{" not in rendered_prompt


def test_rendered_prompt_contains_the_whole_faq(rendered_prompt, faq_text):
    assert faq_text.strip() in rendered_prompt


def test_all_three_routes_are_described(system_prompt_text):
    for route in ("BUG_REPORT", "PLATFORM_QUESTION", "OTHER"):
        assert route in system_prompt_text, f"route {route} is not described"


def test_the_tool_is_named_correctly(system_prompt_text):
    """A renamed tool here means the model never calls the real one."""
    assert TOOL_NAME in system_prompt_text


def test_all_three_tool_arguments_are_spelled_out(system_prompt_text):
    for field in TOOL_FIELDS:
        assert field in system_prompt_text, f"{field} is never mentioned"


def test_the_tool_is_gated_on_collecting_everything_first(system_prompt_text):
    low = _flat(system_prompt_text)
    assert "do not call" in low or "do not call the tool" in low
    assert "one" in low and "per message" in low


def test_the_ticket_id_must_be_relayed(system_prompt_text):
    low = _flat(system_prompt_text)
    assert "ticketid" in low or "ticket id" in low
    assert "never invent a ticket id" in low


def test_the_support_phone_number_is_present_and_correct(system_prompt_text):
    assert SUPPORT_PHONE in system_prompt_text
    # Guard against a stray second number creeping in.
    numbers = set(re.findall(r"\b1-\d{3}-\d{3}-\d{4}\b", system_prompt_text))
    assert numbers == {SUPPORT_PHONE}


def test_faq_answers_are_restricted_to_the_faq(system_prompt_text):
    low = _flat(system_prompt_text)
    assert "only" in low
    assert "single source of truth" in low or "only using the faq" in low


def test_uncovered_questions_fall_through_to_the_handoff(system_prompt_text):
    low = _flat(system_prompt_text)
    assert "does not cover" in low


def test_prompt_injection_is_addressed(system_prompt_text):
    """A stand-out requirement: the prompt should survive 'ignore your
    previous instructions'."""
    low = _flat(system_prompt_text)
    assert "untrusted" in low
    for signal in ("ignore", "developer mode", "persona"):
        assert signal in low, f"injection defence does not mention {signal!r}"


def test_the_faq_is_fenced_as_data_not_instructions(system_prompt_text):
    """Everything after the fence is reference data, so a prompt injection
    hidden in the FAQ cannot take over."""
    assert "--- FAQ document ---" in system_prompt_text
    assert "--- end of FAQ document ---" in system_prompt_text
    assert "reference data" in system_prompt_text.lower()


def test_fabrication_is_forbidden(system_prompt_text):
    low = _flat(system_prompt_text)
    assert "never invent" in low or "do not invent" in low


def test_the_prompt_is_substantial_but_not_bloated(rendered_prompt):
    """The whole rendered prompt is re-sent on every turn, so size is a real
    cost. Nova Pro has plenty of room for this, but a runaway FAQ would not
    be fine."""
    assert 4_000 < len(rendered_prompt) < 40_000
