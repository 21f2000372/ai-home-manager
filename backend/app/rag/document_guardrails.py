from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set


@dataclass
class GuardrailResult:
    allowed: bool
    status: str
    reason: Optional[str] = None


MIN_EXTRACTED_TEXT_LENGTH = 20
MIN_CLASSIFICATION_CONFIDENCE = 0.60

SUPPORTED_DOCUMENT_DOMAINS: Set[str] = {
    "Finance",
    "Food",
    "Maintenance",
    "Tasks",
}


def check_extracted_text(
    text: str,
) -> GuardrailResult:
    cleaned = " ".join(
        (text or "").strip().split()
    )

    if not cleaned:
        return GuardrailResult(
            allowed=False,
            status="rejected",
            reason="No readable text was detected in the document.",
        )

    if len(cleaned) < MIN_EXTRACTED_TEXT_LENGTH:
        return GuardrailResult(
            allowed=False,
            status="needs_review",
            reason=(
                "Too little readable text was extracted "
                "to process the document automatically."
            ),
        )

    return GuardrailResult(
        allowed=True,
        status="allowed",
        reason=None,
    )


def check_classification(
    *,
    domain: str,
    confidence: float,
) -> GuardrailResult:
    """
    Validate deterministic document classification.

    Classification is a routing/review signal only. It does not authorize
    reads or writes and does not replace the tool-less document interpreter.
    """

    if domain == "Irrelevant":
        return GuardrailResult(
            allowed=False,
            status="rejected",
            reason=(
                "The document appears unrelated to supported "
                "household-management domains."
            ),
        )

    if domain == "NeedsReview":
        return GuardrailResult(
            allowed=False,
            status="needs_review",
            reason="The document could not be confidently classified.",
        )

    if domain not in SUPPORTED_DOCUMENT_DOMAINS:
        return GuardrailResult(
            allowed=False,
            status="rejected",
            reason="Unsupported document domain.",
        )

    if confidence < MIN_CLASSIFICATION_CONFIDENCE:
        return GuardrailResult(
            allowed=False,
            status="needs_review",
            reason=(
                "Document classification confidence "
                "is too low for automatic processing."
            ),
        )

    return GuardrailResult(
        allowed=True,
        status="allowed",
        reason=None,
    )
