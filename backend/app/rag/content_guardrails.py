from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Pattern, Tuple


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


# These signatures detect instruction structure rather than isolated words.
# Broad terms such as "print", "note", "user", or "AI" must not cause a
# rejection by themselves because they can occur in legitimate documents.
PROMPT_INJECTION_REGEX_PATTERNS: Tuple[
    Tuple[str, Pattern[str]],
    ...,
] = (
    (
        "instruction_addressed_to_ai",
        re.compile(
            r"\b(?:note|instruction|instructions)\s+"
            r"(?:for|to)\s+(?:(?:an?|the)\s+)?"
            r"(?:ai|assistant|model|llm)"
            r"(?:\s+(?:reader|agent|system))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "override_the_user",
        re.compile(
            r"\b(?:ignore|disregard|override)\s+"
            r"(?:the\s+)?user(?:'s)?"
            r"(?:\s+(?:request|instruction|instructions|intent))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "canary_output_command",
        re.compile(
            r"\b(?:print|output|return|respond\s+with|include)\s+"
            r"(?:the\s+)?(?:token\s+)?"
            r"canary(?:[-_: ]?[a-z0-9]+)*"
            r"(?:\s+in\s+(?:your|the)\s+"
            r"(?:reply|response|answer|output))?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "ai_role_directive",
        re.compile(
            r"\b(?:ai\s+assistant|assistant|llm|model)\s*:\s*"
            r"(?:add|assign|call|create|delete|execute|list|mark|"
            r"output|print|read|reveal|run|send|show|update)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "protected_document_disclosure",
        re.compile(
            r"\b(?:expose|list|read|return|reveal|show)\s+"
            r"(?:all\s+)?(?:stored|private|other\s+users?'?)\s+"
            r"documents?\b",
            re.IGNORECASE,
        ),
    ),
)


_OCR_CANARY_TOKEN_RE = re.compile(
    r"\b([a-z0-9]{4,10})[-_: ]([0-9]{3,8})\b",
    re.IGNORECASE,
)


def _normalize_ocr_fragment(value: str) -> str:
    return value.casefold().translate(
        str.maketrans(
            {
                "0": "o",
                "1": "l",
                "5": "s",
                "8": "b",
            }
        )
    )


def _similarity(value: str, expected: str) -> float:
    return SequenceMatcher(
        None,
        _normalize_ocr_fragment(value),
        expected,
    ).ratio()


def _contains_fuzzy_ocr_injection(text: str) -> bool:
    """Recognize a damaged canary plus damaged override instruction."""

    has_canary = False
    for candidate, _suffix in _OCR_CANARY_TOKEN_RE.findall(text):
        if _similarity(candidate, "canary") >= 0.65:
            has_canary = True
            break

    if not has_canary:
        return False

    words = re.findall(r"[a-z0-9]+", text.casefold())
    instruction_words = (
        "disregard",
        "ignore",
        "instructions",
        "override",
    )

    for word in words:
        if any(
            _similarity(word, expected) >= 0.65
            for expected in instruction_words
        ):
            return True

    for index in range(len(words) - 1):
        phrase = words[index] + words[index + 1]
        if _similarity(phrase, "listabove") >= 0.62:
            return True

    return False


def check_untrusted_document_text(
    text: str,
) -> ContentGuardrailResult:
    """Detect prompt-injection-like instructions in untrusted text."""

    normalized = " ".join(text.lower().split())

    if not normalized:
        return ContentGuardrailResult(
            safe=True,
            status="allowed",
            reason=None,
            matched_patterns=[],
        )

    matched = [
        pattern
        for pattern in sorted(PROMPT_INJECTION_PATTERNS)
        if pattern in normalized
    ]

    matched.extend(
        label
        for label, signature in PROMPT_INJECTION_REGEX_PATTERNS
        if signature.search(normalized)
    )

    if (
        "canary_output_command" not in matched
        and _contains_fuzzy_ocr_injection(normalized)
    ):
        matched.append("fuzzy_handwritten_injection")

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
