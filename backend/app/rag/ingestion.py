from __future__ import annotations

from werkzeug.datastructures import FileStorage

from app.rag.content_guardrails import (
    check_untrusted_document_text,
)
from app.rag.document_classifier import (
    classify_document,
)
from app.rag.document_guardrails import (
    check_classification,
    check_extracted_text,
)
from app.rag.document_image_detector import (
    check_image_is_document,
)
from app.rag.duplicate_detector import (
    calculate_sha256,
    calculate_text_hash,
    calculate_visual_hashes,
    find_exact_duplicate,
    find_text_duplicate,
    find_visual_near_duplicate,
)
from app.rag.file_validation import (
    validate_file,
)
from app.rag.text_extraction import (
    extract_text,
)
from app.storage.temp_storage import (
    delete_temp_file,
    save_temp_upload,
)
import json
from typing import Optional

from app.db.base import SessionLocal
from app.models.documents import PendingDocumentUpload


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}


def stage_uploaded_file(
    uploaded_file: FileStorage,
    uploaded_by: Optional[str] = None,
) -> dict:

    # 1. Save temporarily
    try:
        staged = save_temp_upload(
            uploaded_file
        )
    except Exception as exc:
        return {
            "success": False,
            "status": "rejected",
            "reason": (
                "Unable to save uploaded file: "
                + str(exc)
            ),
        }

    temp_path = staged["temp_path"]

    # 2. Validate
    validation = validate_file(
        temp_path
    )

    if not validation.valid:
        delete_temp_file(
            temp_path
        )

        return {
            "success": False,
            "status": "rejected",
            "reason": validation.reason,
            "original_filename": staged[
                "original_filename"
            ],
        }

    # 3. SHA-256 fingerprint
    sha256_hash = calculate_sha256(
        temp_path
    )
    session = SessionLocal()

    try:
        exact_duplicate = find_exact_duplicate(
            session,
            sha256_hash,
        )
    finally:
        session.close()

    if exact_duplicate is not None:
        delete_temp_file(
            temp_path
        )

        return {
            "success": False,
            "status": "rejected",
            "reason": "Exact duplicate document detected.",
            "duplicate": exact_duplicate,
            "original_filename": staged[
                "original_filename"
            ],
        }
    # 4. Image document check
    image_check = None

    if validation.extension in IMAGE_EXTENSIONS:
        image_check = check_image_is_document(
            temp_path
        )

        if not image_check.is_document:
            delete_temp_file(
                temp_path
            )

            return {
                "success": False,
                "status": "rejected",
                "reason": image_check.reason,
                "original_filename": staged[
                    "original_filename"
                ],
                "document_check": {
                    "is_document": (
                        image_check.is_document
                    ),
                    "confidence": (
                        image_check.confidence
                    ),
                    "reason": (
                        image_check.reason
                    ),
                },
            }

    # 5. Extract text
    extraction = extract_text(
        temp_path
    )

    if not extraction.success:
        delete_temp_file(
            temp_path
        )

        return {
            "success": False,
            "status": "rejected",
            "reason": extraction.reason,
            "original_filename": staged[
                "original_filename"
            ],
        }

    # 6. Normalized text hash
    text_hash = calculate_text_hash(
        extraction.text
    )
    session = SessionLocal()

    try:
        text_duplicate = find_text_duplicate(
            session,
            text_hash,
        )
    finally:
        session.close()

    if text_duplicate is not None:
        delete_temp_file(
            temp_path
        )

        return {
            "success": False,
            "status": "rejected",
            "reason": (
                "A document with identical extracted "
                "content already exists."
            ),
            "duplicate": text_duplicate,
            "original_filename": staged[
                "original_filename"
            ],
        }
    # 7. Text guardrail
    text_guardrail = check_extracted_text(
        extraction.text
    )

    if (
        not text_guardrail.allowed
        and text_guardrail.status == "rejected"
    ):
        delete_temp_file(
            temp_path
        )

        return {
            "success": False,
            "status": "rejected",
            "reason": text_guardrail.reason,
            "original_filename": staged[
                "original_filename"
            ],
        }

    text_needs_review = (
        text_guardrail.status
        == "needs_review"
    )

    # 8. Prompt injection guardrail
    content_guardrail = (
        check_untrusted_document_text(
            extraction.text
        )
    )

    security_needs_review = (
        not content_guardrail.safe
    )

    # 9. Classification
    classification = classify_document(
        extraction.text
    )

    # 10. Classification guardrail
    classification_guardrail = (
        check_classification(
            domain=classification.domain,
            confidence=(
                classification.confidence
            ),
        )
    )

    if (
        not classification_guardrail.allowed
        and classification_guardrail.status
        == "rejected"
    ):
        delete_temp_file(
            temp_path
        )

        return {
            "success": False,
            "status": "rejected",
            "reason": (
                classification_guardrail.reason
            ),
            "original_filename": staged[
                "original_filename"
            ],
            "classification": {
                "domain": (
                    classification.domain
                ),
                "document_type": (
                    classification.document_type
                ),
                "confidence": (
                    classification.confidence
                ),
                "reason": (
                    classification.reason
                ),
            },
        }

    classification_needs_review = (
        classification_guardrail.status
        == "needs_review"
    )

    # 11. Visual hashes
    visual_hashes = []

    if validation.extension in IMAGE_EXTENSIONS:
        try:
            visual_hashes = (
                calculate_visual_hashes(
                    temp_path
                )
            )
        except Exception:
            visual_hashes = []
    visual_duplicate = None

    if visual_hashes:
        session = SessionLocal()

        try:
            visual_duplicate = (
                find_visual_near_duplicate(
                    session,
                    visual_hashes,
                )
            )
        finally:
            session.close()
    visual_needs_review = (
        visual_duplicate is not None
    )
    # 12. Final status
    needs_review = any(
        [
            text_needs_review,
            security_needs_review,
            classification_needs_review,
            visual_needs_review,
        ]
    )   
    if visual_needs_review:
        review_reasons.append(
            "A visually similar document already exists. "
            "Review before confirming."
        )
    
    final_status = (
        "needs_review"
        if needs_review
        else "staged"
    )

    # 13. Final result
    result = {
        "success": True,
        "status": final_status,

        "upload_id": staged[
            "upload_id"
        ],

        "original_filename": staged[
            "original_filename"
        ],

        "safe_filename": staged[
            "safe_filename"
        ],

        "temp_path": temp_path,

        "validation": {
            "extension": (
                validation.extension
            ),
            "mime_type": (
                validation.mime_type
            ),
            "file_size": (
                validation.file_size
            ),
        },

        "extraction": {
            "method": (
                extraction.method
            ),
            "page_count": (
                extraction.page_count
            ),
            "text": (
                extraction.text
            ),
        },

        "classification": {
            "domain": (
                classification.domain
            ),
            "document_type": (
                classification.document_type
            ),
            "confidence": (
                classification.confidence
            ),
            "reason": (
                classification.reason
            ),
        },

        "security": {
            "prompt_injection_detected": (
                not content_guardrail.safe
            ),
            "matched_patterns": (
                content_guardrail.matched_patterns
                or []
            ),
        },

        "duplicate_fingerprints": {
            "sha256": (
                sha256_hash
            ),
            "normalized_text_hash": (
                text_hash
            ),
            "visual_hashes": (
                visual_hashes
            ),
        },
        "duplicate_check": {
            "visual_near_duplicate": visual_duplicate,
        },
    }

    if image_check is not None:
        result[
            "document_check"
        ] = {
            "is_document": (
                image_check.is_document
            ),
            "confidence": (
                image_check.confidence
            ),
            "reason": (
                image_check.reason
            ),
        }

    if needs_review:
        review_reasons = []

        if text_needs_review:
            review_reasons.append(
                text_guardrail.reason
            )

        if security_needs_review:
            review_reasons.append(
                content_guardrail.reason
            )

        if classification_needs_review:
            review_reasons.append(
                classification_guardrail.reason
            )

        result[
            "review_reasons"
        ] = [
            reason
            for reason in review_reasons
            if reason
        ]

    session = SessionLocal()

    try:
        pending = PendingDocumentUpload(
            upload_id=staged["upload_id"],
            uploaded_by=uploaded_by,

            original_filename=staged[
                "original_filename"
            ],

            safe_filename=staged[
                "safe_filename"
            ],

            temp_path=temp_path,

            mime_type=validation.mime_type,
            extension=validation.extension,
            file_size=validation.file_size,

            sha256=sha256_hash,
            normalized_text_hash=text_hash,

            visual_hashes_json=json.dumps(
                visual_hashes
            ),

            extracted_text=extraction.text,

            extraction_method=(
                extraction.method
            ),

            page_count=(
                extraction.page_count
            ),

            domain=(
                classification.domain
            ),

            classified_document_type=(
                classification.document_type
            ),

            classification_confidence=(
                classification.confidence
            ),

            classification_reason=(
                classification.reason
            ),

            prompt_injection_detected=(
                not content_guardrail.safe
            ),

            status=final_status,

            review_reasons_json=json.dumps(
                result.get(
                    "review_reasons",
                    [],
                )
            ),
        )

        session.add(pending)
        session.commit()
        session.refresh(pending)

        result["pending_id"] = (
            pending.pending_id
        )

    except Exception as exc:
        session.rollback()

        # The file should not remain orphaned if
        # database staging failed.
        delete_temp_file(
            temp_path
        )

        return {
            "success": False,
            "status": "rejected",
            "reason": (
                "Unable to save pending "
                "document metadata: "
                + str(exc)
            ),
            "original_filename": staged[
                "original_filename"
            ],
        }

    finally:
        session.close()

    return result