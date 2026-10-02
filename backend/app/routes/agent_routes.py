"""Chat and document endpoints for the LangGraph household agent.



Compatible with Python 3.9.

"""



from __future__ import annotations



import base64

import binascii

import io

import logging

import re

from typing import Any, Dict, List, Optional, Tuple



from flask import Blueprint, g, jsonify, request

from werkzeug.datastructures import FileStorage



from app.ai.agents.graph import run_agent

from app.ai.agents.tools.tasks_tools import (

    reset_agent_user_id,

    set_agent_user_id,

)

from app.auth.decorators import login_required

from app.config import config

from app.services.conversation_scope import (

    ConversationScopeError,

    resolve_conversation_scope,

)





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

    conversation_id: str,

    uploaded_file: Optional[FileStorage] = None,

):

    """Run the agent using authenticated server-side identity.



    Conversation and session ownership must be validated before this

    function is called. The client cannot supply user_id or role.

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

    """Build a frontend-safe document review response."""



    ingestion = (

        result.get("document_ingestion_result")

        or {}

    )

    classification = (

        ingestion.get("classification")

        or {}

    )

    review = result.get("document_review") or {}

    proposal = review.get("proposal") or {}



    public_actions: List[Dict[str, Any]] = []



    for action in proposal.get("actions") or []:

        if not isinstance(action, dict):

            continue



        evidence_pages: List[Any] = []



        for item in action.get("evidence") or []:

            if not isinstance(item, dict):

                continue



            page = item.get("page")



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

            proposal.get("warnings")

            or []

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





_CLOUDINARY_DOWNLOAD_URL_RE = re.compile(
    r"https://api\.cloudinary\.com/[^\s]+",
    re.IGNORECASE,
)


def _sanitize_public_text(value: Any) -> Any:
    """Remove internal identifiers and signed URLs from user-facing text."""

    if not isinstance(value, str):
        return value

    # A signed Cloudinary URL is machine data. Never rewrite its UUID and then
    # expose the now-invalid URL in conversational text.
    cleaned = _CLOUDINARY_DOWNLOAD_URL_RE.sub(
        "[secure document link available]",
        value,
    )

    cleaned = re.sub(
        r"\s*,?\s*\bid\s*=\s*" + _UUID_RE.pattern,
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    return _UUID_RE.sub(
        "[internal-id]",
        cleaned,
    )


def _public_original_document(
    result: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    """Return an untouched signed Cloudinary URL as structured API data.

    Only completed document actions are considered. The URL is allow-listed
    to Cloudinary's API download endpoint and must look like an authenticated,
    signed download URL.
    """

    from urllib.parse import parse_qs, urlsplit

    for action in result.get("planned_actions") or []:
        if not isinstance(action, dict):
            continue

        if str(action.get("domain") or "").strip().casefold() != "documents":
            continue

        if str(action.get("status") or "").strip().casefold() != "completed":
            continue

        raw_result = action.get("result")
        if not isinstance(raw_result, str):
            continue

        filename = None
        download_url = None

        for raw_line in raw_result.splitlines():
            line = raw_line.strip()

            if line.casefold().startswith("original document:"):
                filename = line.split(":", 1)[1].strip() or None
                continue

            if line.casefold().startswith("download link:"):
                download_url = line.split(":", 1)[1].strip() or None

        if not filename or not download_url:
            continue

        try:
            parsed = urlsplit(download_url)
        except ValueError:
            continue

        if parsed.scheme != "https":
            continue

        if (parsed.hostname or "").casefold() != "api.cloudinary.com":
            continue

        query = parse_qs(parsed.query, keep_blank_values=True)

        if query.get("type", [""])[0] != "authenticated":
            continue

        required_query_fields = (
            "timestamp",
            "public_id",
            "format",
            "signature",
            "api_key",
        )
        if any(not query.get(field) for field in required_query_fields):
            continue

        return {
            "filename": filename,
            "download_url": download_url,
        }

    return None





def _public_planned_actions(

    actions: Any,

) -> List[Dict[str, Any]]:

    """Return only frontend-safe action information."""



    public: List[Dict[str, Any]] = []



    for action in actions or []:

        if not isinstance(action, dict):

            continue



        public.append(

            {

                "description": action.get(

                    "description"

                ),

                "domain": action.get("domain"),

                "intent": action.get("intent"),

                "status": action.get("status"),

                "result": _sanitize_public_text(

                    action.get("display_result")
                    or action.get("result")

                ),

            }

        )



    return public





def _is_document_result(

    result: Dict[str, Any],

    had_uploaded_file: bool,

) -> bool:

    """Return whether a graph result belongs to document processing."""



    if had_uploaded_file:

        return True



    if (

        result.get("document_ingestion_result")

        is not None

    ):

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

) -> Optional[Dict[str, Any]]:

    """Build a frontend-safe document execution summary."""



    status = str(

        result.get("document_execution_status")

        or ""

    ).strip()



    if not status:

        return None



    actions: List[Dict[str, Any]] = []



    for item in (

        result.get("document_execution_results")

        or []

    ):

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





def _public_cross_domain_suggestion(

    result: Dict[str, Any],

) -> Optional[Dict[str, Any]]:

    """Return frontend-safe suggestion information."""



    suggestion = result.get("active_suggestion")



    if not isinstance(suggestion, dict):

        return None



    return {

        "description": suggestion.get(

            "description"

        ),

        "target_domain": suggestion.get(

            "target_domain"

        ),

        "missing_fields": list(

            suggestion.get("missing_fields")

            or []

        ),

    }





def _decode_json_file(

    file_payload: Any,

) -> Tuple[Optional[FileStorage], Optional[str]]:

    """Convert a base64 JSON attachment to FileStorage.



    Expected input:



        {

            "filename": "bill.pdf",

            "content_type": "application/pdf",

            "data_base64": "<base64 bytes>"

        }



    The attachment is optional.

    """



    if file_payload is None:

        return None, None



    if not isinstance(file_payload, dict):

        return None, "file must be an object"



    filename_value = file_payload.get("filename")



    if not isinstance(filename_value, str):

        return None, "file.filename must be a string"



    filename = filename_value.strip()



    if not filename:

        return None, "file.filename is required"



    content_type_value = file_payload.get(

        "content_type"

    )



    if content_type_value is None:

        content_type = "application/octet-stream"

    elif isinstance(content_type_value, str):

        content_type = content_type_value.strip()

        if not content_type:

            content_type = "application/octet-stream"

    else:

        return (

            None,

            "file.content_type must be a string",

        )



    encoded = file_payload.get("data_base64")



    if (

        not isinstance(encoded, str)

        or not encoded.strip()

    ):

        return (

            None,

            "file.data_base64 is required",

        )



    encoded = encoded.strip()



    # Accept browser-generated data URLs.

    if (

        encoded.startswith("data:")

        and "," in encoded

    ):

        encoded = encoded.split(",", 1)[1]



    # Base64 is approximately four-thirds the size of

    # its decoded binary data.

    max_encoded_chars = (

        ((int(config.MAX_UPLOAD_BYTES) + 2) // 3)

        * 4

        + 16

    )



    if len(encoded) > max_encoded_chars:

        return (

            None,

            "uploaded file exceeds the maximum "

            "allowed size",

        )



    try:

        raw = base64.b64decode(

            encoded,

            validate=True,

        )

    except (binascii.Error, ValueError):

        return (

            None,

            "file.data_base64 is not valid base64",

        )



    if len(raw) > int(config.MAX_UPLOAD_BYTES):

        return (

            None,

            "uploaded file exceeds the maximum "

            "allowed size",

        )



    uploaded_file = FileStorage(

        stream=io.BytesIO(raw),

        filename=filename,

        content_type=content_type,

    )



    return uploaded_file, None


_DOCUMENT_REJECTION_HTTP_STATUS = {
    "document_domain_forbidden": 403,
    "document_exact_duplicate": 409,
    "document_validation_failed": 422,
}


def _document_rejection_status(
    ingestion: Dict[str, Any],
) -> int:
    """Map trusted ingestion rejection codes to stable HTTP semantics.

    Reason matching is retained only for responses created by an older worker
    during a rolling deployment. New ingestion code emits ``error_code``.
    """

    error_code = str(
        ingestion.get("error_code") or ""
    ).strip()
    mapped = _DOCUMENT_REJECTION_HTTP_STATUS.get(error_code)
    if mapped is not None:
        return mapped

    reason = str(
        ingestion.get("reason") or ""
    ).strip()
    if reason.startswith(
        "You do not have permission to upload documents"
    ):
        return 403
    if "duplicate" in reason.casefold():
        return 409
    return 422


@agent_bp.route(

    "/message",

    methods=["POST"],

)

@login_required

def agent_request():

    """Process an authenticated chat or document request.



    The frontend may omit conversation_id and session_id.



    When both are omitted, the server creates a new conversation.



    When either identifier is supplied, the server resolves and

    validates it against the authenticated user before running the

    agent.



    Every response after scope resolution returns both identifiers.

    """



    if not request.is_json:

        return jsonify(

            {

                "error": (

                    "Content-Type application/json "

                    "is required"

                )

            }

        ), 415



    data = request.get_json(

        silent=True

    )



    if not isinstance(data, dict):

        return jsonify(

            {

                "error": (

                    "JSON object body is required"

                )

            }

        ), 400



    message_value = data.get("message")



    if not isinstance(message_value, str):

        return jsonify(

            {

                "error": (

                    "message must be a string"

                )

            }

        ), 400



    message = message_value.strip()



    if not message:

        return jsonify(

            {

                "error": "message is required"

            }

        ), 400



    uploaded_file, file_error = (

        _decode_json_file(

            data.get("file")

        )

    )



    if file_error:

        return jsonify(

            {

                "error": file_error

            }

        ), 400



    had_uploaded_file = (

        uploaded_file is not None

    )



    scope = None



    try:

        try:

            # Raw request values are passed to the ownership

            # service. This prevents numbers, lists, and objects

            # from becoming identifiers through str().

            scope = resolve_conversation_scope(

                user_id=g.current_user.user_id,

                conversation_id=data.get(

                    "conversation_id"

                ),

                session_id=data.get(

                    "session_id"

                ),

            )

        except ConversationScopeError as exc:

            return jsonify(

                {

                    "error": exc.public_message

                }

            ), exc.status_code



        result = _run_for_current_user(

            message=message,

            session_id=scope.session_id,

            conversation_id=(

                scope.conversation_id

            ),

            uploaded_file=uploaded_file,

        )



    except Exception:

        logger.exception(

            "Agent request failed"

        )



        error_payload = {

            "error": (

                "Unable to process the request."

            )

        }



        if scope is not None:

            error_payload["conversation_id"] = (

                scope.conversation_id

            )

            error_payload["session_id"] = (

                scope.session_id

            )



        return jsonify(

            error_payload

        ), 500



    finally:

        if uploaded_file is not None:

            uploaded_file.close()



    # IDs returned to the client come from the verified

    # ownership scope, not from graph-generated state.

    conversation_id = scope.conversation_id

    session_id = scope.session_id



    if not _is_document_result(

        result,

        had_uploaded_file,

    ):

        return jsonify(

            {

                "mode": "chat",

                "response": result.get(

                    "response"

                ),

                "planned_actions": (

                    _public_planned_actions(

                        result.get(

                            "planned_actions",

                            [],

                        )

                    )

                ),

                "document": _public_original_document(result),

                "interaction_id": result.get(

                    "interaction_id"

                ),

                "conversation_id": (

                    conversation_id

                ),

                "session_id": session_id,

                "awaiting_confirmation": bool(

                    result.get(

                        "awaiting_confirmation"

                    )

                ),

                "suggestion": (

                    _public_cross_domain_suggestion(

                        result

                    )

                ),

                "error": result.get(

                    "auth_error"

                ),

            }

        ), 200



    ingestion = (

        result.get(

            "document_ingestion_result"

        )

        or {}

    )



    if (

        ingestion

        and not ingestion.get(

            "success",

            False,

        )

    ):

        classification = (

            ingestion.get("classification")

            or {}

        )



        domain = str(

            classification.get("domain")

            or ""

        ).strip()



        reason = (

            ingestion.get("reason")

            or "The document was rejected."

        )



        status_code = _document_rejection_status(
            ingestion
        )



        return jsonify(

            {

                "mode": "document",

                "status": "rejected",

                "response": (

                    result.get("response")

                    or reason

                ),

                "reason": reason,

                "classification": {

                    "domain": (

                        domain or None

                    ),

                    "document_type": (

                        classification.get(

                            "document_type"

                        )

                    ),

                    "confidence": (

                        classification.get(

                            "confidence"

                        )

                    ),

                },

                "conversation_id": (

                    conversation_id

                ),

                "session_id": session_id,

                "interaction_id": result.get(

                    "interaction_id"

                ),

            }

        ), status_code



    execution = (

        _public_document_execution(

            result

        )

    )



    public_review = None



    if (

        ingestion

        or result.get("document_review")

        is not None

    ):

        public_review = (

            _public_document_review(

                result

            )

        )



    execution_status = str(

        result.get(

            "document_execution_status"

        )

        or ""

    ).strip()



    if execution_status:

        response_status = (

            execution_status.lower()

        )

    else:

        response_status = (

            ingestion.get("status")

            or "processed"

        )



    payload = {

        "mode": "document",

        "status": response_status,

        "response": _sanitize_public_text(

            result.get("response")

        ),

        "conversation_id": conversation_id,

        "session_id": session_id,

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



    return jsonify(

        payload

    ), 200
