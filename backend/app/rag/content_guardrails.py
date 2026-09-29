from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ContentGuardrailResult:
    safe: bool
    status: str
    reason: Optional[str] = None
    matched_patterns: Optional[List[str]] = None


PROMPT_INJECTION_PATTERNS = {
    "ignore previous instructions",
    "ignore all previous instructions",
    "ignore prior instructions",
    "disregard previous instructions",
    "forget previous instructions",
    "forget all previous instructions",

    "reveal the system prompt",
    "show the system prompt",
    "print the system prompt",
    "tell me your system prompt",
    "system prompt",

    "reveal developer instructions",
    "show developer instructions",
    "developer message",

    "you are now",
    "new instructions",
    "follow these instructions",

    "call the tool",
    "execute the tool",
    "run this command",
    "execute this command",

    "delete all expenses",
    "delete all records",
    "delete everything",
    "drop database",
    "drop table",

    "bypass authentication",
    "bypass authorization",
    "bypass security",
    "disable security",

    "override policy",
    "ignore policy",
    "ignore safety",
}


def check_untrusted_document_text(
    text: str,
) -> ContentGuardrailResult:
    """
    Detect obvious prompt-injection-like instructions
    inside extracted document text.

    Important:
    Document text must always be treated as untrusted data,
    even when no suspicious pattern is detected.
    """

    normalized = " ".join(
        text.lower().split()
    )

    if not normalized:
        return ContentGuardrailResult(
            safe=True,
            status="allowed",
            reason=None,
            matched_patterns=[],
        )

    matched = [
        pattern
        for pattern in PROMPT_INJECTION_PATTERNS
        if pattern in normalized
    ]

    if matched:
        return ContentGuardrailResult(
            safe=False,
            status="needs_review",
            reason=(
                "Document contains text that resembles "
                "prompt-injection or executable instructions."
            ),
            matched_patterns=matched,
        )

    return ContentGuardrailResult(
        safe=True,
        status="allowed",
        reason=None,
        matched_patterns=[],
    )