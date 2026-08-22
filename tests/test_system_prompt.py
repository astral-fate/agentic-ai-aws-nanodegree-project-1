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


# --- rules added after the first live run on AWS ---------------------------
#
# The first end-to-end run against Nova Pro exposed three behaviours the
# baseline prompt did not prevent, all of them invisible to the offline
# suite. Each now has a rule in the prompt and a test here.
# See docs/EVALUATION.md, "Run 1".


def test_the_first_bug_reply_is_always_a_question(system_prompt_text):
    """Live run: Nova called create_bug_report on turn 1, fabricating the
    steps and environment to satisfy the required fields. "Do not call the
    tool before you have all three" is a negative constraint with no
    checkable trigger; "your first reply is always a question" has one."""
    low = _flat(system_prompt_text)

    assert "first reply to a bug report is always a question" in low
    assert "never a tool call" in low


def test_inventing_field_values_is_forbidden(system_prompt_text):
    """The Lambda rejects blank fields, so a model that wants to call the
    tool early invents plausible values instead. That is worse than a blank:
    engineering chases a bug nobody reported."""
    low = _flat(system_prompt_text)

    assert "never invent a value" in low
    assert "placeholder" in low


def test_duplicate_tickets_are_called_out_as_harmful(system_prompt_text):
    """Live run: the model filed a second ticket on the next turn, saying it
    had "updated" the first. Saying "exactly once" was not enough - the
    prompt now explains that no update path exists."""
    low = _flat(system_prompt_text)

    assert "exactly once per problem" in low
    assert "no way to update a ticket" in low


def test_reasoning_tags_are_forbidden(system_prompt_text):
    """Live run: replies began with "<thinking> The customer is reporting a
    bug...". That reaches the customer verbatim, and pollutes the evaluation
    dataset the judge scores."""
    low = _flat(system_prompt_text)

    assert "<thinking>" in low
    assert "never write out your reasoning" in low


def test_other_is_stated_as_the_default_category(system_prompt_text):
    """Live run: asked for a brownie recipe, Nova concluded the message fitted
    "none of the categories" - while listing OTHER as one of them - and
    skipped the hand-off. OTHER has to read as the catch-all."""
    low = _flat(system_prompt_text)

    assert "the default" in low
    assert "never a message that fits" in low
