"""Chat and document endpoints for the LangGraph household agent."""
from __future__ import annotations

import base64
import binascii
import io
import logging
import re
from typing import Any, Dict, List

from flask import Blueprint, g, jsonify, request
from werkzeug.datastructures import FileStorage

from app.ai.agents.graph import run_agent
from app.config import config
from app.ai.agents.tools.tasks_tools import (
    reset_agent_user_id,
    set_agent_user_id,
)
from app.auth.decorators import login_required


logger = logging.getLogger(__name__)

agent_bp = Blueprint(
    "agent",
    __name__,
    url_prefix="/api/agent",
)


def _run_for_current_user(
    *,
    message: str,
    session_id: str,
    conversation_id=None,
    uploaded_file=None,
):
    """
    Invoke LangGraph with identity and role taken only from authenticated
    server-side Flask context.

    The client never supplies user_id or role.
    """

    user_token = set_agent_user_id(
        g.current_user.user_id
    )

    try:
        return run_agent(
            message=message,
            session_id=session_id,
            user_id=g.current_user.user_id,
            role=g.current_role.value,
            conversation_id=conversation_id,
            uploaded_file=uploaded_file,
        )
    finally:
        reset_agent_user_id(user_token)


def _public_document_review(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a frontend-safe document-review payload.

    Internal proposal ids, pending-document ids, temp paths, storage keys,
    database row ids, and raw extracted document text are intentionally not
    returned by this HTTP route.
    """

    ingestion = result.get(
        "document_ingestion_result"
    ) or {}
    classification = ingestion.get(
        "classification"
    ) or {}

    review = result.get("document_review") or {}
    proposal = review.get("proposal") or {}

    public_actions: List[Dict[str, Any]] = []

    for action in proposal.get("actions") or []:
        evidence_pages = []

        for item in action.get("evidence") or []:
            page = (item or {}).get("page")

            if (
                page is not None
                and page not in evidence_pages
            ):
                evidence_pages.append(page)

        public_actions.append(
            {
                "description": (
                    action.get("description")
                    or action.get("operation")
                    or "Proposed action"
                ),
                "status": (
                    "blocked"
                    if action.get("blocked")
                    else "ready"
                ),
                "evidence_pages": evidence_pages,
                "unresolved_fields": list(
                    action.get("unresolved_fields")
                    or []
                ),
                "blocked_reason": action.get(
                    "blocked_reason"
                ),
                "user_corrections": list(
                    action.get("user_corrections")
                    or []
                ),
            }
        )

    return {
        "status": ingestion.get("status"),
        "classification": {
            "domain": classification.get("domain"),
            "document_type": classification.get(
                "document_type"
            ),
            "confidence": classification.get(
                "confidence"
            ),
        },
        "summary": proposal.get("summary"),
        "warnings": list(
            proposal.get("warnings") or []
        ),
        "actions": public_actions,
        "clarification_required": bool(
            proposal.get("clarification_required")
        ),
        "clarification_question": proposal.get(
            "clarification_question"
        ),
    }


_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-"
    r"[0-9a-fA-F]{4}-"
    r"[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-"
    r"[0-9a-fA-F]{12}\b"
)


def _sanitize_public_text(value: Any) -> Any:
    """Remove internal UUIDs from user-facing free-text tool results."""

    if not isinstance(value, str):
        return value

    cleaned = re.sub(
        r"\s*,?\s*\bid\s*=\s*" + _UUID_RE.pattern,
        "",
        value,
        flags=re.IGNORECASE,
    )

    return _UUID_RE.sub("[internal-id]", cleaned)


def _public_planned_actions(
    actions: Any,
) -> List[Dict[str, Any]]:
    """
    Return only frontend-safe normal-chat action information.

    Tool names/arguments and stable database identifiers stay server-side.
    """

    public: List[Dict[str, Any]] = []

    for action in actions or []:
        if not isinstance(action, dict):
            continue

        public.append(
            {
                "description": action.get("description"),
                "domain": action.get("domain"),
                "intent": action.get("intent"),
                "status": action.get("status"),
                "result": _sanitize_public_text(
                    action.get("result")
                ),
            }
        )

    return public



def _is_document_result(
    result: Dict[str, Any],
    uploaded_file: Any,
) -> bool:
    """Return True when this graph result belongs to the document workflow."""

    if uploaded_file is not None:
        return True

    if result.get("document_ingestion_result") is not None:
        return True

    if result.get("document_review") is not None:
        return True

    if result.get("document_execution_status"):
        return True

    resolution = str(
        result.get("confirmation_resolution")
        or ""
    ).strip()

    return resolution.startswith("document_")


def _public_document_execution(
    result: Dict[str, Any],
):
    """Build a frontend-safe document execution summary."""

    status = str(
        result.get("document_execution_status")
        or ""
    ).strip()

    if not status:
        return None

    actions: List[Dict[str, Any]] = []

    for item in result.get("document_execution_results") or []:
        if not isinstance(item, dict):
            continue

        actions.append(
            {
                "status": item.get("status"),
                "summary": _sanitize_public_text(
                    item.get("summary")
                ),
                "replayed": bool(
                    item.get("replayed")
                ),
            }
        )

    return {
        "status": status,
        "archived": bool(
            result.get("archived_document_id")
        ),
        "actions": actions,
    }

def _decode_json_file(file_payload: Any):
    """
    Convert an optional JSON attachment into Werkzeug FileStorage.

    Expected shape:
        {
            "filename": "bill.pdf",
            "content_type": "application/pdf",
            "data_base64": "<base64 bytes>"
        }

    Returns:
        (FileStorage | None, error_message | None)
    """

    if file_payload is None:
        return None, None

    if not isinstance(file_payload, dict):
        return None, "file must be an object"

    filename = str(
        file_payload.get("filename")
        or ""
    ).strip()

    content_type = str(
        file_payload.get("content_type")
        or "application/octet-stream"
    ).strip()

    encoded = file_payload.get("data_base64")

    if not filename:
        return None, "file.filename is required"

    if not isinstance(encoded, str) or not encoded.strip():
        return None, "file.data_base64 is required"

    encoded = encoded.strip()

    # Permit a browser-style data URL while keeping the documented contract
    # as plain base64.
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]

    # Reject obviously oversized JSON attachments before allocating the
    # decoded byte buffer. Base64 expands binary content by roughly 4/3.
    max_encoded_chars = (
        ((int(config.MAX_UPLOAD_BYTES) + 2) // 3) * 4
        + 16
    )

    if len(encoded) > max_encoded_chars:
        return None, "uploaded file exceeds the maximum allowed size"

    try:
        raw = base64.b64decode(
            encoded,
            validate=True,
        )
    except (binascii.Error, ValueError):
        return None, "file.data_base64 is not valid base64"

    if len(raw) > int(config.MAX_UPLOAD_BYTES):
        return None, "uploaded file exceeds the maximum allowed size"

    return FileStorage(
        stream=io.BytesIO(raw),
        filename=filename,
        content_type=content_type,
    ), None


@agent_bp.route(
    "/message",
    methods=["POST"],
)
@login_required
def agent_request():
    """
    Authenticated JSON-only agent message endpoint.

    Request:
        Content-Type: application/json

        {
            "message": "required user message",
            "session_id": "optional",
            "conversation_id": "optional",
            "file": {
                "filename": "optional attachment filename",
                "content_type": "application/pdf",
                "data_base64": "base64 encoded bytes"
            }
        }

    Behavior:
        message only       -> normal agent flow
        message + file     -> document flow
        file without text  -> rejected

    Identity and role always come from authenticated Flask context.
    The client cannot choose or override user_id or role.
    """

    if not request.is_json:
        return jsonify(
            {
                "error": (
                    "Content-Type application/json is required"
                ),
            }
        ), 415

    data = request.get_json(
        silent=True,
    )

    if not isinstance(data, dict):
        return jsonify(
            {
                "error": "JSON object body is required",
            }
        ), 400

    message = str(
        data.get("message")
        or ""
    ).strip()

    if not message:
        return jsonify(
            {
                "error": "message is required",
            }
        ), 400

    uploaded_file, file_error = _decode_json_file(
        data.get("file")
    )

    if file_error:
        return jsonify(
            {
                "error": file_error,
            }
        ), 400

    session_id = (
        str(
            data.get("session_id")
            or ""
        ).strip()
        or g.current_user.user_id
    )

    conversation_id = (
        str(
            data.get("conversation_id")
            or ""
        ).strip()
        or None
    )

    try:
        result = _run_for_current_user(
            message=message,
            session_id=session_id,
            conversation_id=conversation_id,
            uploaded_file=uploaded_file,
        )
    except Exception:
        logger.exception(
            "Agent request failed"
        )
        return jsonify(
            {
                "error": (
                    "Unable to process the request."
                ),
            }
        ), 500

    # --------------------------------------------------------------
    # Normal chat response
    # --------------------------------------------------------------
    if not _is_document_result(
        result,
        uploaded_file,
    ):
        return jsonify(
            {
                "mode": "chat",
                "response": result.get("response"),
                "planned_actions": _public_planned_actions(
                    result.get(
                        "planned_actions",
                        [],
                    )
                ),
                "interaction_id": result.get(
                    "interaction_id"
                ),
                "conversation_id": result.get(
                    "conversation_id"
                ),
                "awaiting_confirmation": bool(
                    result.get(
                        "awaiting_confirmation"
                    )
                ),
                "error": result.get(
                    "auth_error"
                ),
            }
        ), 200

    # --------------------------------------------------------------
    # Document response
    # --------------------------------------------------------------
    ingestion = result.get(
        "document_ingestion_result"
    ) or {}

    if ingestion and not ingestion.get(
        "success",
        False,
    ):
        classification = ingestion.get(
            "classification"
        ) or {}

        domain = str(
            classification.get("domain") or ""
        ).strip()

        reason = (
            ingestion.get("reason")
            or "The document was rejected."
        )

        if reason.startswith(
            "You do not have permission to upload "
            "documents in the "
        ):
            status_code = 403
        elif "duplicate" in reason.lower():
            status_code = 409
        else:
            status_code = 422

        return jsonify(
            {
                "mode": "document",
                "status": "rejected",
                "response": result.get(
                    "response"
                ) or reason,
                "reason": reason,
                "classification": {
                    "domain": domain or None,
                    "document_type": classification.get(
                        "document_type"
                    ),
                    "confidence": classification.get(
                        "confidence"
                    ),
                },
                "conversation_id": result.get(
                    "conversation_id"
                ),
                "interaction_id": result.get(
                    "interaction_id"
                ),
            }
        ), status_code

    execution = _public_document_execution(
        result
    )

    public_review = None
    if (
        ingestion
        or result.get("document_review") is not None
    ):
        public_review = _public_document_review(
            result
        )

    execution_status = str(
        result.get("document_execution_status")
        or ""
    ).strip()

    response_status = (
        execution_status.lower()
        if execution_status
        else (
            ingestion.get("status")
            or "processed"
        )
    )

    payload = {
        "mode": "document",
        "status": response_status,
        "response": _sanitize_public_text(
            result.get("response")
        ),
        "conversation_id": result.get(
            "conversation_id"
        ),
        "interaction_id": result.get(
            "interaction_id"
        ),
        "awaiting_confirmation": bool(
            result.get(
                "awaiting_confirmation"
            )
        ),
    }

    if public_review is not None:
        payload["document"] = public_review

    if execution is not None:
        payload["execution"] = execution

    return jsonify(payload), 200
