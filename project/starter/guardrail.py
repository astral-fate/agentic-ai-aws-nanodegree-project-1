"""Screen a customer message with a Bedrock Guardrail before the model runs.

Kept separate from ``chat_guarded.py`` so the screening logic can be unit
tested without a terminal loop, and reused by any other caller.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_BLOCK_MESSAGE = (
    "I am sorry, I cannot help with that request. If you need support, "
    "please call our team on 1-800-555-0199, Monday to Friday."
)


@dataclass
class Verdict:
    """The outcome of screening one message."""

    allowed: bool
    message: str = ""
    reasons: List[str] = field(default_factory=list)
    raw: Optional[Dict[str, Any]] = None

    def __bool__(self) -> bool:
        return self.allowed


def _reasons(assessments: List[Dict[str, Any]]) -> List[str]:
    """Human-readable summary of why the guardrail intervened."""
    out: List[str] = []
    for assessment in assessments or []:
        for f in assessment.get("contentPolicy", {}).get("filters", []):
            if f.get("action") == "BLOCKED":
                out.append(f"content filter: {f.get('type')}")
        for t in assessment.get("topicPolicy", {}).get("topics", []):
            if t.get("action") == "BLOCKED":
                out.append(f"denied topic: {t.get('name')}")
        for w in assessment.get("wordPolicy", {}).get("customWords", []):
            if w.get("action") == "BLOCKED":
                out.append(f"blocked word: {w.get('match')}")
        for p in assessment.get("sensitiveInformationPolicy", {}).get("piiEntities", []):
            if p.get("action") == "BLOCKED":
                out.append(f"pii: {p.get('type')}")
    return out


def screen(
    client,
    text: str,
    guardrail_id: str,
    guardrail_version: str,
    source: str = "INPUT",
    block_message: str = DEFAULT_BLOCK_MESSAGE,
) -> Verdict:
    """Run `text` through the guardrail.

    Returns a :class:`Verdict`. ``allowed`` is False when the guardrail
    intervened, in which case ``message`` is what to show the customer
    instead of calling the model.

    A guardrail that errors is treated as **fail-open**: the message is
    allowed through and the error is recorded in ``reasons``. The system
    prompt's own injection defences still apply, so a guardrail outage
    degrades protection rather than taking the chatbot offline. Flip this to
    fail-closed if your risk appetite says otherwise.
    """
    if not text.strip():
        return Verdict(allowed=True)

    try:
        response = client.apply_guardrail(
            guardrailIdentifier=guardrail_id,
            guardrailVersion=guardrail_version,
            source=source,
            content=[{"text": {"text": text}}],
        )
    except Exception as exc:  # noqa: BLE001 - surface the real error
        return Verdict(allowed=True, reasons=[f"guardrail unavailable: {exc}"])

    if response.get("action") != "GUARDRAIL_INTERVENED":
        return Verdict(allowed=True, raw=response)

    outputs = response.get("outputs") or []
    message = outputs[0].get("text") if outputs else ""
    return Verdict(
        allowed=False,
        message=message or block_message,
        reasons=_reasons(response.get("assessments", [])),
        raw=response,
    )


def is_configured(config: Dict[str, Any]) -> bool:
    """True if setup_guardrail.py has recorded a guardrail in the config."""
    return bool(config.get("guardrail_id") and config.get("guardrail_version"))
