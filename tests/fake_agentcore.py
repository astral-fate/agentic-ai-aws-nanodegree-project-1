"""An offline stand-in for the Bedrock AgentCore runtime.

Why this exists
---------------
``chat.py`` and ``generate-eval-dataset.py`` talk to a real, managed agent
loop: ``bedrock-agentcore:InvokeHarness`` streams events back, and the tool
call to ``create_bug_report`` happens server-side through the gateway.

None of that can run without an AWS account, which makes the interesting
parts of this project untestable on a laptop. So this module reimplements
the *contract* of that runtime locally:

* the same streaming event shapes (``contentBlockStart`` with a ``toolUse``,
  ``contentBlockDelta`` with text, ``messageStop``),
* the same statefulness across turns, keyed by ``runtimeSessionId``,
* and a tool call that invokes the **real** ``create_bug_report.lambda_handler``
  against a fake DynamoDB table.

What it does and does not prove
-------------------------------
It exercises everything except the model's judgement: the streaming parser,
the tool-call plumbing, the Lambda's validation and DynamoDB write, the
session state that lets a bug report be collected over several turns, and
the JSONL schema handed to Bedrock Evaluations.

The routing itself is done by :class:`ScriptedModel`, a keyword matcher that
mirrors the rules in ``system_prompt.txt``. That makes these tests
deterministic, but it means a green run says "the wiring is correct", not
"Nova routes correctly". Only a real Bedrock Evaluations run can say the
latter - see ``docs/EVALUATION.md``.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, Iterable, List, Optional

from botocore.eventstream import EventStream

SUPPORT_PHONE = "1-800-555-0199"

# ---------------------------------------------------------------------------
# Streaming plumbing
# ---------------------------------------------------------------------------


class FakeEventStream(EventStream):
    """An iterable that passes ``isinstance(x, EventStream)``.

    ``chat.py`` and ``generate-eval-dataset.py`` both locate the streaming
    part of the response with that isinstance check, so the fake has to be a
    real subclass. We deliberately skip ``EventStream.__init__`` (it wants a
    raw HTTP stream and a parser) and override iteration instead.
    """

    def __init__(self, events: Iterable[Dict[str, Any]]):  # noqa: D107
        self._events = list(events)

    def __iter__(self):
        return iter(self._events)


def _text_events(text: str, chunk: int = 24) -> List[Dict[str, Any]]:
    """Break `text` into contentBlockDelta events the way the real API does."""
    events: List[Dict[str, Any]] = []
    for i in range(0, len(text), chunk):
        events.append(
            {"contentBlockDelta": {"delta": {"text": text[i:i + chunk]}}}
        )
    events.append({"messageStop": {"stopReason": "end_turn"}})
    return events


def _tool_use_event(tool_name: str, tool_use_id: str) -> Dict[str, Any]:
    return {
        "contentBlockStart": {
            "start": {"toolUse": {"name": tool_name, "toolUseId": tool_use_id}}
        }
    }


# ---------------------------------------------------------------------------
# Fake DynamoDB
# ---------------------------------------------------------------------------


class FakeTable:
    """The two calls ``create_bug_report.py`` makes on a DynamoDB table."""

    def __init__(self, name: str = "bug-report-tool-stack-bug-reports"):
        self.name = name
        self.items: List[Dict[str, Any]] = []

    def put_item(self, Item: Dict[str, Any]):  # noqa: N803 - boto3 casing
        self.items.append(dict(Item))
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}

    def get_item(self, Key, **_kwargs):  # noqa: N803 - boto3 casing
        """``scripted_bug_report.py`` reads a filed ticket back by id."""
        ticket_id = Key.get("ticketId")
        for item in self.items:
            if item.get("ticketId") == ticket_id:
                return {"Item": dict(item)}
        return {}  # boto3 omits "Item" entirely when nothing matches

    def scan(self, **_kwargs):
        return {"Items": list(self.items), "Count": len(self.items)}


class FakeDynamoResource:
    def __init__(self, table: FakeTable):
        self._table = table

    def Table(self, name: str):  # noqa: N802 - boto3 casing
        self._table.name = name
        return self._table


class FakeClientContext:
    """Mimics the Lambda client context the gateway populates."""

    def __init__(self, tool_name: str = "bugreports___create_bug_report"):
        self.custom = {"bedrockAgentCoreToolName": tool_name}


class FakeLambdaContext:
    def __init__(self, tool_name: str = "bugreports___create_bug_report"):
        self.client_context = FakeClientContext(tool_name)
        self.function_name = "bug-report-tool-stack-create-bug-report"
        self.aws_request_id = str(uuid.uuid4())


# ---------------------------------------------------------------------------
# The scripted model
# ---------------------------------------------------------------------------

# Unambiguous "the software is broken" signals. These win over an FAQ
# keyword match, because the prompt says a 500 on the payment page is a bug
# even though the sentence also contains the word "returns".
_STRONG_BUG_SIGNALS = (
    "crash", "500", "404", "blank", "spinner", "spins", "frozen", "freeze",
    "stuck", "does nothing", "won't load", "wont load", "glitch", "bug",
    "can't add", "cant add", "white screen",
)

# Weaker signals: only a bug if the FAQ has nothing to say about the message.
_WEAK_BUG_SIGNALS = (
    "error", "broken", "break", "not working", "doesn't work", "fails",
    "failing",
)

_INJECTION_SIGNALS = (
    "ignore all previous", "ignore previous", "ignore your", "developer mode",
    "system prompt", "verbatim", "you are now", "pretend you are", "act as",
    "disregard", "reveal your", "print your",
)

# Account-specific actions the assistant must not perform.
_ACCOUNT_ACTION_SIGNALS = (
    "cancel order", "cancel my order", "refund my", "my order #",
    "change my address", "resend my invoice", "look up my order",
)

_ENV_SIGNALS = (
    "chrome", "safari", "firefox", "edge", "opera", "windows", "macos",
    "mac os", "sonoma", "ios", "android", "iphone", "ipad", "linux",
    "desktop", "laptop", "tablet", "browser",
)

_STEP_SIGNALS = (
    "step", "first", "then", "click", "go to", "navigate", "add to cart",
    "checkout", "1.", "2.", "open the", "i type", "i search", "log in",
)

# question keyword -> the FAQ-grounded answer the scripted model gives.
_FAQ_ANSWERS = (
    (("return", "send back", "send it back"),
     "You can return most items within 30 days of delivery, as long as they "
     "are unused and in the original packaging, unless the item arrived "
     "defective. Contact support with your order number to start a return."),
    (("refund", "money back"),
     "Refunds go back to the original payment method once we have received "
     "and inspected the return. That usually takes 3-10 business days, "
     "depending on your bank or provider."),
    (("track", "tracking", "where is my order"),
     "Once your order ships we email you a tracking link. If you have an "
     "account, you can also find tracking under My Orders."),
    (("account to", "guest", "need an account"),
     "No, you can check out as a guest. Creating an account just lets you "
     "track orders, save addresses and check out faster next time."),
    (("damaged", "defective", "arrived broken"),
     "Please contact us within 7 days of delivery with photos of the item, "
     "the packaging and the shipping label. We will arrange a replacement "
     "or a refund."),
    # Checked before the promo-code entry: "a gift card and a promo code"
    # mentions both, and the gift-card answer is the one that fits.
    (("gift card", "store credit"),
     "Yes. A gift card is treated as a payment method, so you can combine it "
     "with one promo code on the same order."),
    (("promo", "discount code", "coupon"),
     "Enter the code at checkout in the promo or discount field and apply it "
     "before paying. Only one code can be used unless stated otherwise."),
    (("declined", "payment failed", "card was declined"),
     "Payments are usually declined because of incorrect billing details, "
     "insufficient funds, a bank security check, or limits on international "
     "or online purchases. You can try again, use a different method, or "
     "check with your bank."),
    (("delivered but", "says delivered", "missing package", "package is late",
      "late package"),
     "Please check the latest tracking updates, your mailbox, any neighbours "
     "and any safe-place note from the carrier. If it still has not turned "
     "up 24 hours after being marked delivered, contact support and we will "
     "investigate."),
    (("shipping cost", "how much does shipping"),
     "Shipping is calculated at checkout based on your destination and the "
     "delivery speed you choose. Any free-shipping promotion shows up "
     "automatically."),
    (("password",),
     "Use the Forgot password link on the sign-in page. If the address "
     "matches an account, you will get a reset email."),
)

_HANDOFF = (
    "I am sorry, that is not something I can help with from this chat. "
    f"Please call our support team on {SUPPORT_PHONE}, Monday to Friday, "
    "and they will be able to help you."
)


def _matches(text: str, signals: Iterable[str]) -> bool:
    low = text.lower()
    return any(s in low for s in signals)


class _BugState:
    """What the assistant has collected so far in one session."""

    def __init__(self):
        self.description: Optional[str] = None
        self.steps: Optional[str] = None
        self.environment: Optional[str] = None
        self.filed = False
        self.asked_for: List[str] = []

    def missing(self) -> Optional[str]:
        if not self.description:
            return "description"
        if not self.steps:
            return "stepsToReproduce"
        if not self.environment:
            return "environment"
        return None


class ScriptedModel:
    """Keyword router that mirrors the rules in ``system_prompt.txt``."""

    def __init__(self):
        self.sessions: Dict[str, _BugState] = {}

    # -- routing ----------------------------------------------------------
    def classify(self, session_id: str, text: str) -> str:
        state = self.sessions.get(session_id)
        # An in-flight bug report keeps control until the ticket is filed,
        # so short answers like "Chrome" are read as replies, not new asks.
        if state and not state.filed:
            return "bug_report"
        if _matches(text, _INJECTION_SIGNALS):
            return "other"
        if _matches(text, _ACCOUNT_ACTION_SIGNALS):
            return "other"
        if _matches(text, _STRONG_BUG_SIGNALS):
            return "bug_report"
        if self._faq_answer(text):
            return "platform_question"
        if _matches(text, _WEAK_BUG_SIGNALS) or text.strip().lower() in {
            "site broken", "broken", "it's broken", "its broken"
        }:
            return "bug_report"
        return "other"

    @staticmethod
    def _faq_answer(text: str) -> Optional[str]:
        low = text.lower()
        for keys, answer in _FAQ_ANSWERS:
            if any(k in low for k in keys):
                return answer
        return None

    # -- behaviours -------------------------------------------------------
    def respond(self, session_id: str, text: str, tool_runner) -> List[Dict[str, Any]]:
        route = self.classify(session_id, text)
        if route == "platform_question":
            return _text_events(self._faq_answer(text) or _HANDOFF)
        if route == "other":
            return _text_events(_HANDOFF)
        return self._bug_report(session_id, text, tool_runner)

    def _bug_report(self, session_id, text, tool_runner) -> List[Dict[str, Any]]:
        state = self.sessions.setdefault(session_id, _BugState())

        # Fold whatever this turn supplied into the collected state.
        if state.description is None:
            # Too vague to file: ask for a sharper description first.
            if len(text.split()) <= 2:
                state.asked_for.append("description")
                return _text_events(
                    "I am sorry you are running into trouble. Could you tell "
                    "me a little more about what exactly is not working?"
                )
            state.description = text.strip()
            # Customers often volunteer their environment in the opening
            # message ("...I'm on Safari on an iPhone"). They almost never
            # give ordered repro steps there, so we do not read steps from
            # the same sentence - that would file a ticket whose
            # stepsToReproduce is just a restatement of the complaint.
            if _matches(text, _ENV_SIGNALS):
                state.environment = text.strip()
        else:
            last_asked = state.asked_for[-1] if state.asked_for else None
            if state.steps is None and _matches(text, _STEP_SIGNALS):
                state.steps = text.strip()
            elif state.environment is None and _matches(text, _ENV_SIGNALS):
                state.environment = text.strip()
            elif state.steps is None and last_asked == "stepsToReproduce":
                # A reply with no obvious keywords is still an answer to the
                # question we just asked.
                state.steps = text.strip()
            elif state.environment is None and last_asked == "environment":
                state.environment = text.strip()

        missing = state.missing()
        if missing == "stepsToReproduce":
            state.asked_for.append("stepsToReproduce")
            return _text_events(
                "Thanks for reporting that. Could you walk me through the "
                "steps you take that lead to the problem?"
            )
        if missing == "environment":
            state.asked_for.append("environment")
            return _text_events(
                "Thank you. Which browser and operating system or device are "
                "you using?"
            )
        if missing == "description":
            state.asked_for.append("description")
            return _text_events(
                "Could you describe what is going wrong in a bit more detail?"
            )

        # Everything collected -> file exactly one ticket.
        tool_use_id = str(uuid.uuid4())
        events: List[Dict[str, Any]] = [
            _tool_use_event("bugreports___create_bug_report", tool_use_id)
        ]
        result = tool_runner(
            {
                "description": state.description,
                "stepsToReproduce": state.steps,
                "environment": state.environment,
            }
        )
        state.filed = True
        if "ticketId" in result:
            events += _text_events(
                f"Thank you. I have filed ticket {result['ticketId']} for you, "
                "and the engineering team will follow up on it."
            )
        else:
            events += _text_events(
                "I was not able to file that ticket just now. Please call our "
                f"support team on {SUPPORT_PHONE}, Monday to Friday."
            )
        return events


# ---------------------------------------------------------------------------
# The fake client
# ---------------------------------------------------------------------------


class FakeAgentCoreRuntime:
    """Stands in for ``boto3.client("bedrock-agentcore")``."""

    def __init__(self, lambda_handler, table: FakeTable):
        self._lambda_handler = lambda_handler
        self.table = table
        self.model = ScriptedModel()
        self.calls: List[Dict[str, Any]] = []
        self.tool_invocations: List[Dict[str, Any]] = []

    def _run_tool(self, args: Dict[str, Any]) -> Dict[str, Any]:
        self.tool_invocations.append(dict(args))
        return self._lambda_handler(args, FakeLambdaContext())

    def invoke_harness(self, **kwargs):
        # Record the call so tests can assert the contract the real API needs.
        self.calls.append(kwargs)

        for required in ("harnessArn", "runtimeSessionId", "messages"):
            if required not in kwargs:
                raise ValueError(f"invoke_harness missing {required!r}")
        session_id = kwargs["runtimeSessionId"]
        if len(session_id) < 33:
            raise ValueError("runtimeSessionId must be at least 33 characters")

        messages = kwargs["messages"]
        user_text = messages[-1]["content"][0]["text"]

        events = self.model.respond(session_id, user_text, self._run_tool)
        return {
            "runtimeSessionId": session_id,
            "responseStream": FakeEventStream(events),
        }
