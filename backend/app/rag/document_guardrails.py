from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

@dataclass
class GuardrailResult:
    allowed: bool
    status: str
    reason: Optional[str] = None


# Minimum amount of extracted text before we trust the document enough
# to continue automatically.
MIN_EXTRACTED_TEXT_LENGTH = 20

# Classification below this level should go to manual review.
MIN_CLASSIFICATION_CONFIDENCE = 0.60


def check_extracted_text(
    text: str,
) -> GuardrailResult:
    """
    Validate extracted OCR/PDF text.

    Possible statuses:
        allowed
        needs_review
        rejected
    """

    cleaned = " ".join(
        text.strip().split()
    )

    # No text at all.
    if not cleaned:
        return GuardrailResult(
            allowed=False,
            status="rejected",
            reason="No readable text was detected in the document.",
        )

    # Some text exists, but not enough to trust automatically.
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
    Validate the result of document classification.

    Supported domains:
        Finance
        Maintenance

    Irrelevant documents are rejected.
    Uncertain documents go to review.
    """

    if domain == "Irrelevant":
        return GuardrailResult(
            allowed=False,
            status="rejected",
            reason=(
                "The document is unrelated to supported "
                "Finance or Maintenance domains."
            ),
        )

    if domain == "NeedsReview":
        return GuardrailResult(
            allowed=False,
            status="needs_review",
            reason=(
                "The document could not be confidently classified."
            ),
        )

    if domain not in {
        "Finance",
        "Maintenance",
    }:
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