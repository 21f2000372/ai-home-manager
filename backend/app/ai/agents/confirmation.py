"""Durable confirmation and editable-review handling for AI Home Manager.



Step 7.1 of the production refactor.



This module keeps normal-chat approvals durable in ``workflow_proposals`` and

adds a safe edit loop.  A user may approve, reject, or describe changes to a

pending action.  Edits do not mutate the stored tool call in-place.  Instead,

the exact pending action is restored as edit context, the planner/specialist

produce a revised complete action, duplicate/consistency checks run again, and

the same durable proposal is advanced to a new revision.



Compatibility target: Python 3.8+.



Document proposals remain owned by the dedicated document workflow introduced

in the next step.  The same revision semantics must be reused there.

"""



from __future__ import annotations



import hashlib

import json

import re

from datetime import timedelta

from typing import Any, Dict, Optional, Tuple

from uuid import uuid4



from langchain_core.messages import AIMessage

from sqlalchemy import desc



from app.ai.agents.state import AgentState

from app.db.base import SessionLocal, utcnow

from app.models.workflows import WorkflowProposal

from app.services.document_workflow import (

    DOCUMENT_ACTION_KIND,

    DocumentWorkflowError,

    approve_document_action_review,

    approve_document_interpretation,

    approve_document_review,

    load_pending_document_action_review,

    load_pending_document_review,

    reject_document_action_review,

    reject_document_review,

    retry_failed_document_review,

)

from app.services.document_execution import (

    find_resumable_document_execution,

)

from app.services.suggestion_workflow import (

    SuggestionWorkflowError,

    begin_suggestion_details,

    complete_replan_suggestion,

    load_pending_suggestion,

    reject_pending_suggestion,

)





YES_RESPONSES = {

    "yes",

    "y",

    "yeah",

    "yep",

    "confirm",

    "confirmed",

    "proceed",

    "do it",

    "add it",

    "continue",

    "ok",

    "okay",

    "approve",

    "approved",

    "yes please",

    "yes, please",

}



NO_RESPONSES = {

    "no",

    "n",

    "nope",

    "cancel",

    "stop",

    "don't",

    "do not",

    "skip it",

    "reject",

    "rejected",

    "decline",

    "declined",

    "deny",

    "denied",

    "no thanks",

    "no, thanks",

}


DOCUMENT_VERIFY_AND_SAVE_RESPONSES = {
    "verify and save",
    "approve and save",
    "confirm and save",
    "correct and save",
    "yes save it",
    "yes save the document",
    "save the document",
    "store the document",
}


DOCUMENT_VERIFY_WITHOUT_STORAGE_RESPONSES = {
    "verify without saving",
    "approve without saving",
    "confirm without saving",
    "use without saving",
    "do not save the document",
    "dont save the document",
    "do not store the document",
    "dont store the document",
}

RETRY_RESPONSES = {

    "retry",

    "try again",

}



EDIT_ONLY_RESPONSES = {

    "edit",

    "edit it",

    "edit that",

    "change",

    "change it",

    "change that",

    "modify",

    "modify it",

    "modify that",

    "revise",

    "revise it",

    "update it",

    "update that",

}



EDIT_PREFIXES = (

    "edit ",

    "change ",

    "modify ",

    "revise ",

    "update ",

    "add ",

    "increase ",

    "make it ",

    "make that ",

    "set ",

    "replace ",

    "assign ",

    "move ",

    "reschedule ",

    "use ",

    "instead ",

    "rather ",

    "actually ",

)



DEFAULT_CONFIRMATION_TTL_HOURS = 24

_CHAT_CONFIRMATION_KINDS = (

    "duplicate",

    "conflict",

    "action",

)

_EDITABLE_CONFIRMATION_KINDS = (

    *_CHAT_CONFIRMATION_KINDS,

    "suggestion",

)

_ROUTABLE_CONFIRMATION_KINDS = (

    "document",

    DOCUMENT_ACTION_KIND,

    "suggestion",

    *_CHAT_CONFIRMATION_KINDS,

)





class ConfirmationPersistenceError(RuntimeError):

    """Raised when a review request cannot be safely persisted/restored."""





def _normalize_reply(message: str) -> str:

    value = " ".join(

        (message or "").casefold().strip().split()

    )



    # Ignore only punctuation surrounding the complete reply. Internal

    # punctuation/text remains intact, so "yes, but change it" is not treated

    # as a pure approval.

    value = re.sub(

        r"^[^\w]+|[^\w]+$",

        "",

        value,

        flags=re.UNICODE,

    )



    return " ".join(value.split())





def _confirmation_key(state: AgentState) -> str:

    """Return the stable conversation/session key used for proposal lookup."""



    return str(

        state.get("session_id")

        or state.get("conversation_id")

        or ""

    ).strip()





def _required_confirmation_scope_value(

    state: AgentState,

    field: str,

    max_length: int,

) -> str:

    """Read one required trusted confirmation-scope identifier."""



    value = state.get(field)

    if not isinstance(value, str):

        raise ConfirmationPersistenceError(

            "{} is required for confirmation routing.".format(field)

        )



    cleaned = value.strip()

    if (

        not cleaned

        or cleaned != value

        or len(cleaned) > max_length

        or any(

            character.isspace()

            or not character.isprintable()

            for character in cleaned

        )

    ):

        raise ConfirmationPersistenceError(

            "{} has an invalid value.".format(field)

        )



    return cleaned





def _confirmation_scope(

    state: AgentState,

) -> Tuple[str, str, str]:

    """Return exact user, conversation, and session scope."""



    return (

        _required_confirmation_scope_value(state, "user_id", 36),

        _required_confirmation_scope_value(state, "conversation_id", 36),

        _required_confirmation_scope_value(state, "session_id", 100),

    )





def _proposal_is_expired(

    proposal: WorkflowProposal,

    now=None,

) -> bool:

    """Check expiry without mutating a workflow owned by another service."""



    expires_at = proposal.expires_at

    if expires_at is None:

        return False



    comparable_now = now or utcnow()

    if expires_at.tzinfo is None and comparable_now.tzinfo is not None:

        comparable_now = comparable_now.replace(tzinfo=None)

    elif expires_at.tzinfo is not None and comparable_now.tzinfo is None:

        comparable_now = comparable_now.replace(tzinfo=expires_at.tzinfo)



    return expires_at <= comparable_now





def _query_most_recent_pending_workflow(

    session,

    state: AgentState,

) -> Optional[WorkflowProposal]:

    """Select the newest non-expired workflow without kind priority."""



    user_id, conversation_id, session_id = _confirmation_scope(state)

    now = utcnow()

    candidates = (

        session.query(WorkflowProposal)

        .filter(

            WorkflowProposal.user_id == user_id,

            WorkflowProposal.conversation_id == conversation_id,

            WorkflowProposal.session_id == session_id,

            WorkflowProposal.status == "AWAITING_REVIEW",

            WorkflowProposal.kind.in_(_ROUTABLE_CONFIRMATION_KINDS),

        )

        .order_by(

            desc(WorkflowProposal.updated_at),

            desc(WorkflowProposal.created_at),

            desc(WorkflowProposal.proposal_id),

        )

        .limit(50)

        .all()

    )



    for proposal in candidates:

        if not _proposal_is_expired(proposal, now):

            return proposal



    return None





def _select_pending_workflow(

    state: AgentState,

) -> Optional[Dict[str, str]]:

    """Return detached routing metadata for the newest pending workflow."""



    session = SessionLocal()

    try:

        proposal = _query_most_recent_pending_workflow(

            session,

            state,

        )

        if proposal is None:

            return None



        return {

            "proposal_id": str(proposal.proposal_id),

            "kind": str(proposal.kind),

        }

    finally:

        session.close()





def _parse_decision(message: str) -> Optional[str]:

    """Parse deliberately explicit yes/no replies."""



    value = _normalize_reply(message)



    if value in YES_RESPONSES:

        return "yes"



    if value in NO_RESPONSES:

        return "no"



    return None


def _parse_document_storage_choice(message: str) -> Optional[bool]:
    """Parse only explicit complete replies for the document storage gate."""

    value = re.sub(
        r"[^\w]+",
        " ",
        (message or "").casefold(),
        flags=re.UNICODE,
    )
    value = " ".join(value.split())

    if value in DOCUMENT_VERIFY_AND_SAVE_RESPONSES:
        return True
    if value in DOCUMENT_VERIFY_WITHOUT_STORAGE_RESPONSES:
        return False
    return None





def _edit_request_kind(message: str) -> Optional[str]:

    """Return ``prompt`` or ``detailed`` for conservative edit requests.



    We intentionally do not treat every non-yes/no message as an edit because

    the user may abandon a pending review and ask an unrelated question.

    """



    value = _normalize_reply(message)



    if not value:

        return None



    if value in EDIT_ONLY_RESPONSES:

        return "prompt"



    if value in _KEEP_EXISTING_RESPONSES:

        return "detailed"



    if value.startswith(EDIT_PREFIXES):

        return "detailed"



    return None









_QUANTITY_TOKEN_RE = re.compile(

    r"(?<![\w.])(\d+(?:\.\d+)?)\s*([a-zA-Z]+)?\b"

)



_EXPLICIT_SET_PREFIXES = (

    "update ",

    "change ",

    "make ",

    "set ",

    "replace ",

)



_EXPLICIT_ADD_PREFIXES = (

    "add ",

    "increase ",

)



_KEEP_EXISTING_RESPONSES = {

    "keep it",

    "keep existing",

    "keep the existing one",

    "keep current",

    "keep current quantity",

    "leave it",

    "leave it as is",

    "leave as is",

}



_UNIT_ALIASES = {

    "kg": "kg",

    "kgs": "kg",

    "kilogram": "kg",

    "kilograms": "kg",

    "g": "g",

    "gm": "g",

    "gms": "g",

    "gram": "g",

    "grams": "g",

    "l": "litre",

    "lt": "litre",

    "ltr": "litre",

    "litre": "litre",

    "litres": "litre",

    "liter": "litre",

    "liters": "litre",

    "ml": "ml",

    "millilitre": "ml",

    "millilitres": "ml",

    "milliliter": "ml",

    "milliliters": "ml",

    "piece": "piece",

    "pieces": "piece",

    "pc": "piece",

    "pcs": "piece",

    "count": "count",

    "unit": "count",

    "units": "count",

}





def _canonical_unit(value: Optional[str]) -> Optional[str]:

    if value is None:

        return None



    normalized = _normalize_reply(value)

    if not normalized:

        return None



    return _UNIT_ALIASES.get(normalized, normalized)





def _explicit_duplicate_quantity_resolution(

    message: str,

    payload: Dict[str, Any],

) -> Optional[Dict[str, Any]]:

    """Resolve explicit low-risk quantity choices deterministically.



    Supported choices for a matched grocery/inventory row are:

    * set the existing quantity (``set/update/change it to 3 kg``),

    * add more of the same unit (``add 2 kg more``), and

    * keep the existing row unchanged (handled as a close/cancel decision).



    The target database id always comes from server-side duplicate detection,

    never from model output or user-provided ids.

    """



    value = _normalize_reply(message)



    match = payload.get("duplicate_match")

    if not isinstance(match, dict):

        return None



    record_type = str(match.get("record_type") or "")

    if record_type not in {"grocery_item", "inventory_item"}:

        return None



    if value in _KEEP_EXISTING_RESPONSES:

        return {

            "mode": "keep",

            "duplicate_match": match,

        }



    if value.startswith(_EXPLICIT_SET_PREFIXES):

        mode = "set"

    elif value.startswith(_EXPLICIT_ADD_PREFIXES):

        mode = "add"

    else:

        return None



    record_id = str(match.get("record_id") or "").strip()

    update_tool = str(match.get("update_tool") or "").strip()

    id_arg = str(match.get("record_id_arg") or "").strip()



    if not record_id or not update_tool or not id_arg:

        return None



    tokens = list(_QUANTITY_TOKEN_RE.finditer(value))

    if not tokens:

        return None



    token = tokens[-1]



    try:

        requested_quantity = float(token.group(1))

    except (TypeError, ValueError):

        return None



    if requested_quantity < 0:

        return None



    requested_unit = _canonical_unit(token.group(2))

    existing_unit = _canonical_unit(match.get("unit"))



    if mode == "add":

        try:

            existing_quantity = float(match.get("quantity"))

        except (TypeError, ValueError):

            return None



        # Adding quantities is safe only when the units are the same (or the

        # user omitted the unit and therefore clearly refers to the existing

        # unit). Unit conversion belongs in the later shared consistency

        # service, not in this confirmation parser.

        if (

            requested_unit is not None

            and existing_unit is not None

            and requested_unit != existing_unit

        ):

            return None



        unit = existing_unit or requested_unit

        quantity = existing_quantity + requested_quantity

    else:

        unit = requested_unit or existing_unit

        quantity = requested_quantity



    args: Dict[str, Any] = {

        id_arg: record_id,

        "quantity": quantity,

    }



    if unit is not None:

        args["unit"] = unit



    display_quantity = (

        str(int(quantity))

        if float(quantity).is_integer()

        else str(quantity)

    )

    display_unit = (" " + unit) if unit else ""



    if mode == "add":

        description = "Set {0} quantity to {1}{2} after adding more.".format(

            match.get("name") or "the existing item",

            display_quantity,

            display_unit,

        )

    else:

        description = "Set {0} quantity to {1}{2}.".format(

            match.get("name") or "the existing item",

            display_quantity,

            display_unit,

        )



    return {

        "mode": mode,

        "tool_name": update_tool,

        "tool_args": args,

        "description": description,

        "duplicate_match": match,

    }





def _close_duplicate_as_keep_existing(

    *,

    session,

    proposal: WorkflowProposal,

    payload: Dict[str, Any],

) -> Dict[str, Any]:

    """Close a duplicate/conflict review without changing the existing row."""



    actions = list(payload.get("planned_actions") or [])

    index = int(payload.get("current_action_index", 0) or 0)



    if 0 <= index < len(actions):

        action = dict(actions[index])

        action["status"] = "cancelled"

        action["result"] = "Kept the existing item unchanged."

        actions[index] = action



    proposal.status = "REJECTED"

    proposal.updated_at = utcnow()

    proposal.last_error = None

    session.commit()



    match = payload.get("duplicate_match") or {}

    name = str(match.get("name") or "the existing item")



    return {

        "confirmation_resolution": "cancelled",

        "confirmation_kind": payload.get("confirmation_kind") or proposal.kind,

        "workflow_proposal_id": str(proposal.proposal_id),

        "editing_workflow_proposal_id": None,

        "pending_edit_context": None,

        "force_action_review": False,

        "planned_actions": actions,

        "current_action_index": index,

        "pending_tool_call": None,

        "pending_ai_message": None,

        "awaiting_confirmation": False,

        "finished": True,

        "response": "Okay, I kept {0} unchanged.".format(name),

    }





def _stage_explicit_duplicate_resolution_for_confirmation(

    *,

    session,

    proposal: WorkflowProposal,

    payload: Dict[str, Any],

    state: AgentState,

    resolution: Dict[str, Any],

) -> Dict[str, Any]:

    """Persist an explicit duplicate resolution as a new review revision.



    The user's resolution (for example ``add 2 kg more``) determines the exact

    update operation, but it is NOT itself treated as final approval.  The

    revised operation is stored as revision N+1 in ``AWAITING_REVIEW`` and the

    user must explicitly confirm it with ``yes`` before authorization/execution.



    This keeps duplicate resolution separate from mutation approval and avoids

    silently changing an existing household record after a clarification turn.

    """



    actions = list(payload.get("planned_actions") or [])

    index = int(payload.get("current_action_index", 0) or 0)



    if not (0 <= index < len(actions)):

        raise ConfirmationPersistenceError(

            "The pending duplicate action cannot be resolved safely."

        )



    revised_action = dict(actions[index])

    revised_action["domain"] = "food"

    revised_action["intent"] = "Update existing item"

    revised_action["description"] = resolution["description"]

    revised_action["status"] = "pending"

    revised_action["result"] = None

    actions[index] = revised_action



    next_revision = int(proposal.revision or 1) + 1

    tool_call_id = "duplicate-resolution-{0}-{1}".format(

        proposal.proposal_id,

        next_revision,

    )



    pending_tool_call = {

        "name": resolution["tool_name"],

        "args": dict(resolution["tool_args"]),

        "id": tool_call_id,

    }



    pending_ai_message = AIMessage(

        content="",

        tool_calls=[

            {

                "name": resolution["tool_name"],

                "args": dict(resolution["tool_args"]),

                "id": tool_call_id,

                "type": "tool_call",

            }

        ],

    )



    revised_payload = dict(payload)

    revised_payload.update(

        {

            "pending_tool_call": pending_tool_call,

            "pending_ai_message": _serialize_ai_message(

                pending_ai_message

            ),

            "planned_actions": actions,

            "current_action_index": index,

            "duplicate_status": "RESOLVED",

            "duplicate_details": (

                "The user explicitly resolved the duplicate by updating "

                "the matched existing item."

            ),

            "duplicate_match": resolution.get("duplicate_match"),

            "confirmation_kind": payload.get("confirmation_kind")

            or proposal.kind,

            "edit_metadata": {

                "edited_from_proposal_id": str(proposal.proposal_id),

                "previous_revision": int(proposal.revision or 1),

                "user_edit_request": str(state.get("message") or ""),

                "explicit_low_risk_resolution": True,

            },

        }

    )



    proposal.revision = next_revision

    proposal.payload_json = _canonical_json(revised_payload)

    proposal.args_hash = _payload_hash(revised_payload)

    proposal.status = "AWAITING_REVIEW"

    proposal.approved_by = None

    proposal.approved_at = None

    proposal.updated_at = utcnow()

    proposal.expires_at = (

        utcnow()

        + timedelta(hours=DEFAULT_CONFIRMATION_TTL_HOURS)

    )

    proposal.last_error = None



    session.commit()

    session.refresh(proposal)



    return {

        "confirmation_resolution": "revised_review",

        "confirmation_kind": payload.get("confirmation_kind") or proposal.kind,

        "workflow_proposal_id": str(proposal.proposal_id),

        "editing_workflow_proposal_id": None,

        "pending_edit_context": None,

        "force_action_review": False,

        "planned_actions": actions,

        "current_action_index": index,

        "pending_tool_call": None,

        "pending_ai_message": None,

        "duplicate_status": "RESOLVED",

        "duplicate_details": revised_payload["duplicate_details"],

        "duplicate_match": resolution.get("duplicate_match"),

        "awaiting_confirmation": True,

        "response": (

            "Proposed update: {0}\n"

            "Reply yes to confirm this update or no to reject it. "

            "You can also tell me what to change."

        ).format(resolution["description"]),

        "finished": True,

    }





def _json_default(value: Any) -> str:

    return str(value)





def _canonical_json(value: Any) -> str:

    """Serialize deterministically so approval binds to one exact revision."""



    return json.dumps(

        value,

        sort_keys=True,

        separators=(",", ":"),

        ensure_ascii=False,

        default=_json_default,

    )





def _payload_hash(payload: Dict[str, Any]) -> str:

    encoded = _canonical_json(payload).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()





def _serialize_ai_message(message: Optional[AIMessage]) -> Optional[Dict[str, Any]]:

    """Serialize only fields needed to resume the original tool call."""



    if message is None:

        return None



    payload: Dict[str, Any] = {

        "content": message.content,

        "additional_kwargs": getattr(

            message,

            "additional_kwargs",

            {},

        ) or {},

        "response_metadata": getattr(

            message,

            "response_metadata",

            {},

        ) or {},

        "tool_calls": getattr(

            message,

            "tool_calls",

            [],

        ) or [],

    }



    message_id = getattr(message, "id", None)

    if message_id is not None:

        payload["id"] = message_id



    message_name = getattr(message, "name", None)

    if message_name is not None:

        payload["name"] = message_name



    return payload





def _deserialize_ai_message(

    payload: Optional[Dict[str, Any]],

) -> Optional[AIMessage]:

    """Rebuild the AI tool-call message required before its ToolMessage."""



    if not payload:

        return None



    kwargs: Dict[str, Any] = {

        "content": payload.get("content", ""),

        "additional_kwargs": payload.get("additional_kwargs") or {},

        "response_metadata": payload.get("response_metadata") or {},

        "tool_calls": payload.get("tool_calls") or [],

    }



    if payload.get("id") is not None:

        kwargs["id"] = payload.get("id")



    if payload.get("name") is not None:

        kwargs["name"] = payload.get("name")



    try:

        return AIMessage(**kwargs)

    except Exception as exc:

        raise ConfirmationPersistenceError(

            "The saved approval message could not be restored."

        ) from exc





def _build_confirmation_payload(state: AgentState) -> Dict[str, Any]:

    """Build the exact normal-chat action payload presented for approval."""



    pending_message = state.get("pending_ai_message")



    if pending_message is not None and not isinstance(

        pending_message,

        AIMessage,

    ):

        raise ConfirmationPersistenceError(

            "Pending confirmation message is not an AIMessage."

        )



    edit_context = state.get("pending_edit_context") or None



    return {

        "pending_tool_call": state.get("pending_tool_call"),

        "pending_ai_message": _serialize_ai_message(pending_message),

        "planned_actions": list(

            state.get("planned_actions") or []

        ),

        "current_action_index": int(

            state.get("current_action_index", 0) or 0

        ),

        "duplicate_status": state.get("duplicate_status"),

        "duplicate_details": state.get("duplicate_details"),

        "duplicate_match": state.get("duplicate_match"),

        "confirmation_kind": (

            state.get("confirmation_kind")

            or "action"

        ),

        "edit_metadata": {

            "edited_from_proposal_id": state.get(

                "editing_workflow_proposal_id"

            ),

            "previous_revision": (

                edit_context.get("revision")

                if isinstance(edit_context, dict)

                else None

            ),

            "user_edit_request": (

                state.get("message")

                if state.get("editing_workflow_proposal_id")

                else None

            ),

        },

    }





def _load_payload(proposal: WorkflowProposal) -> Dict[str, Any]:

    """Load and integrity-check a stored proposal payload."""



    try:

        payload = json.loads(proposal.payload_json)

    except Exception as exc:

        raise ConfirmationPersistenceError(

            "The saved approval request is unreadable."

        ) from exc



    if not isinstance(payload, dict):

        raise ConfirmationPersistenceError(

            "The saved approval request has an invalid payload."

        )



    if _payload_hash(payload) != proposal.args_hash:

        raise ConfirmationPersistenceError(

            "The saved approval request failed its integrity check."

        )



    return payload





def _query_pending_proposal(

    session,

    state: AgentState,

    proposal_id: Optional[str] = None,

) -> Optional[WorkflowProposal]:

    """Return one exact owned, unexpired normal-chat confirmation."""



    user_id, conversation_id, session_id = _confirmation_scope(state)

    query = (

        session.query(WorkflowProposal)

        .filter(

            WorkflowProposal.user_id == user_id,

            WorkflowProposal.conversation_id == conversation_id,

            WorkflowProposal.session_id == session_id,

            WorkflowProposal.status == "AWAITING_REVIEW",

            WorkflowProposal.kind.in_(_EDITABLE_CONFIRMATION_KINDS),

        )

    )



    if proposal_id:

        query = query.filter(

            WorkflowProposal.proposal_id == str(proposal_id)

        )



    proposal = query.order_by(

        desc(WorkflowProposal.updated_at),

        desc(WorkflowProposal.created_at),

    ).first()



    if proposal is None:

        return None



    if _proposal_is_expired(proposal):

        return None



    return proposal





def _query_edit_target(

    session,

    state: AgentState,

    proposal_id: str,

) -> Optional[WorkflowProposal]:

    """Load an editable proposal by internal state, never by user-supplied id."""



    if not proposal_id:

        return None



    user_id, conversation_id, session_id = _confirmation_scope(state)

    query = session.query(WorkflowProposal).filter(

        WorkflowProposal.proposal_id == str(proposal_id),

        WorkflowProposal.user_id == user_id,

        WorkflowProposal.conversation_id == conversation_id,

        WorkflowProposal.session_id == session_id,

        WorkflowProposal.status == "AWAITING_REVIEW",

        WorkflowProposal.kind.in_(_EDITABLE_CONFIRMATION_KINDS),

    )

    proposal = query.first()

    if proposal is not None and _proposal_is_expired(proposal):

        return None

    return proposal





def store_pending_confirmation(state: AgentState) -> str:

    """Persist or revise the exact normal-chat action shown for approval.



    If ``editing_workflow_proposal_id`` is present, the existing durable

    proposal is advanced to revision N+1.  Otherwise a new proposal row is

    created.  Persistence is fail-closed.

    """



    key = _confirmation_key(state)



    if not key:

        raise ConfirmationPersistenceError(

            "Cannot persist confirmation without a session identifier."

        )



    payload = _build_confirmation_payload(state)



    if not payload.get("pending_tool_call"):

        raise ConfirmationPersistenceError(

            "Cannot persist confirmation without a pending tool call."

        )



    payload_json = _canonical_json(payload)

    args_hash = _payload_hash(payload)



    kind = str(

        payload.get("confirmation_kind")

        or "action"

    )



    if kind == "document":

        raise ConfirmationPersistenceError(

            "Document approvals must use the document workflow service."

        )



    session = SessionLocal()



    try:

        user_id = state.get("user_id")

        edit_target_id = state.get("editing_workflow_proposal_id")



        if edit_target_id:

            proposal = _query_edit_target(

                session,

                state,

                str(edit_target_id),

            )



            if proposal is None:

                raise ConfirmationPersistenceError(

                    "The pending action can no longer be edited."

                )



            # Verify the previous revision before replacing it.

            _load_payload(proposal)



            proposal.revision = int(proposal.revision or 0) + 1

            proposal.payload_json = payload_json

            proposal.args_hash = args_hash

            proposal.kind = kind

            proposal.status = "AWAITING_REVIEW"

            proposal.approved_by = None

            proposal.approved_at = None

            proposal.updated_at = utcnow()

            proposal.expires_at = (

                utcnow()

                + timedelta(hours=DEFAULT_CONFIRMATION_TTL_HOURS)

            )

            proposal.last_error = None



            session.commit()

            session.refresh(proposal)



            return str(proposal.proposal_id)



        # Only one unresolved normal-chat approval should be active for a

        # session/user. Keep old rows for audit history, but cancel them.

        existing_query = session.query(WorkflowProposal).filter(

            WorkflowProposal.session_id == key,

            WorkflowProposal.status == "AWAITING_REVIEW",

        )



        if user_id:

            existing_query = existing_query.filter(

                WorkflowProposal.user_id == str(user_id)

            )



        for existing in existing_query.all():

            existing.status = "CANCELLED"

            existing.updated_at = utcnow()

            existing.last_error = (

                "Superseded by a newer confirmation request."

            )



        proposal = WorkflowProposal(

            session_id=key,

            conversation_id=state.get("conversation_id"),

            user_id=(

                str(user_id)

                if user_id

                else None

            ),

            kind=kind,

            revision=1,

            payload_json=payload_json,

            args_hash=args_hash,

            pending_document_id=None,

            status="AWAITING_REVIEW",

            expires_at=(

                utcnow()

                + timedelta(hours=DEFAULT_CONFIRMATION_TTL_HOURS)

            ),

        )



        session.add(proposal)

        session.commit()

        session.refresh(proposal)



        return str(proposal.proposal_id)



    except ConfirmationPersistenceError:

        session.rollback()

        raise

    except Exception as exc:

        session.rollback()

        raise ConfirmationPersistenceError(

            "Unable to persist the approval request."

        ) from exc

    finally:

        session.close()





def _current_action_description(payload: Dict[str, Any]) -> str:

    actions = list(payload.get("planned_actions") or [])

    index = int(payload.get("current_action_index", 0) or 0)



    if 0 <= index < len(actions):

        action = actions[index]

        if isinstance(action, dict):

            return str(

                action.get("description")

                or action.get("intent")

                or "the pending action"

            )



    return "the pending action"







def _resume_suggestion_confirmation(

    state: AgentState,

    pending: Dict[str, Any],

    decision: Optional[str],

    edit_kind: Optional[str],

) -> Dict[str, Any]:

    """Handle a durable cross-domain suggestion without broad memory lookup."""



    proposal_id = str(pending.get("proposal_id") or "")

    payload = dict(pending.get("payload") or {})

    suggestion = dict(payload.get("suggestion") or {})

    stage = str(payload.get("stage") or "offered")

    continuation_mode = str(

        suggestion.get("continuation_mode") or "exact"

    )

    missing_fields = list(suggestion.get("missing_fields") or [])



    if decision == "no":

        try:

            reject_pending_suggestion(state)

        except Exception:

            pass

        return {

            "confirmation_resolution": "cancelled",

            "confirmation_kind": "suggestion",

            "workflow_proposal_id": proposal_id,

            "editing_workflow_proposal_id": None,

            "pending_edit_context": None,

            "suggestion_context": None,

            "active_suggestion": None,

            "awaiting_confirmation": False,

            "finished": True,

            "response": "Okay, I won't do that follow-up action.",

        }



    if decision == "yes" and stage == "offered":

        if missing_fields or continuation_mode == "replan":

            try:

                begin_suggestion_details(state, proposal_id)

            except SuggestionWorkflowError as exc:

                return {

                    "confirmation_resolution": "error",

                    "confirmation_kind": "suggestion",

                    "awaiting_confirmation": False,

                    "finished": True,

                    "response": str(exc),

                }



            detail_prompt = str(

                suggestion.get("detail_prompt")

                or "Tell me the missing details for this follow-up."

            )

            return {

                "confirmation_resolution": "suggestion_details",

                "confirmation_kind": "suggestion",

                "workflow_proposal_id": proposal_id,

                "active_suggestion": suggestion,

                "awaiting_confirmation": True,

                "finished": True,

                "response": detail_prompt,

            }



        target_tool = str(suggestion.get("target_tool") or "").strip()

        target_domain = str(suggestion.get("target_domain") or "").strip()

        known_args = dict(suggestion.get("known_args") or {})

        if not target_tool or not target_domain:

            return {

                "confirmation_resolution": "error",

                "confirmation_kind": "suggestion",

                "awaiting_confirmation": False,

                "finished": True,

                "response": "The saved follow-up suggestion is incomplete.",

            }



        call_id = "suggestion_{0}".format(uuid4().hex)

        pending_tool_call = {

            "name": target_tool,

            "args": known_args,

            "id": call_id,

        }

        pending_ai_message = AIMessage(

            content="",

            tool_calls=[pending_tool_call],

        )

        action = {

            "domain": target_domain,

            "intent": str(suggestion.get("description") or "follow-up"),

            "description": str(

                suggestion.get("description") or "Follow-up action"

            ),

            "tool_name": target_tool,

            "tool_args": known_args,

            "status": "pending",

            "result": None,

            "origin": "cross_domain_suggestion",

        }



        return {

            "confirmation_resolution": "suggestion_confirmed",

            "confirmation_kind": "suggestion",

            "workflow_proposal_id": proposal_id,

            # If duplicate/conflict checks require a second review, revise the

            # same durable suggestion row instead of creating an ambiguous row.

            "editing_workflow_proposal_id": proposal_id,

            "pending_edit_context": None,

            "force_action_review": False,

            "planned_actions": [action],

            "current_action_index": 0,

            "pending_tool_call": pending_tool_call,

            "pending_ai_message": pending_ai_message,

            "duplicate_status": None,

            "duplicate_details": None,

            "duplicate_match": None,

            "active_suggestion": suggestion,

            "awaiting_confirmation": False,

            "finished": False,

            "response": "",

        }



    if stage == "collecting_details" and decision is None:

        if continuation_mode == "replan":

            try:

                complete_replan_suggestion(state, proposal_id)

            except SuggestionWorkflowError as exc:

                return {

                    "confirmation_resolution": "error",

                    "confirmation_kind": "suggestion",

                    "awaiting_confirmation": False,

                    "finished": True,

                    "response": str(exc),

                }



            return {

                "confirmation_resolution": "suggestion_replan",

                "confirmation_kind": "suggestion",

                "workflow_proposal_id": None,

                "editing_workflow_proposal_id": None,

                "pending_edit_context": None,

                "force_action_review": False,

                "planned_actions": [],

                "current_action_index": 0,

                "suggestion_context": {

                    "description": suggestion.get("description"),

                    "source_description": suggestion.get("source_description"),

                    "context_text": suggestion.get("context_text"),

                    "target_domain": suggestion.get("target_domain"),

                },

                "active_suggestion": None,

                "awaiting_confirmation": False,

                "finished": False,

                "response": "",

            }



        target_domain = str(suggestion.get("target_domain") or "")

        target_tool = str(suggestion.get("target_tool") or "")

        known_args = dict(suggestion.get("known_args") or {})

        current_action = {

            "domain": target_domain,

            "intent": str(suggestion.get("description") or "follow-up"),

            "description": str(

                suggestion.get("description") or "Complete follow-up action"

            ),

            "tool_name": target_tool or None,

            "tool_args": known_args,

            "status": "pending",

            "result": None,

            "origin": "cross_domain_suggestion",

        }

        return {

            "confirmation_resolution": "edit",

            "confirmation_kind": "suggestion",

            "workflow_proposal_id": proposal_id,

            "editing_workflow_proposal_id": proposal_id,

            "pending_edit_context": {

                "proposal_id": proposal_id,

                "revision": int(pending.get("revision") or 1),

                "confirmation_kind": "suggestion",

                "current_action_index": 0,

                "current_action": current_action,

                "pending_tool_call": {

                    "name": target_tool,

                    "args": known_args,

                } if target_tool else None,

                "missing_fields": missing_fields,

                "suggestion_context": suggestion.get("context_text"),

            },

            "force_action_review": True,

            "planned_actions": [],

            "current_action_index": 0,

            "active_suggestion": suggestion,

            "awaiting_confirmation": False,

            "finished": False,

            "response": "",

        }



    if edit_kind == "prompt":

        if stage == "offered" and (missing_fields or continuation_mode == "replan"):

            try:

                begin_suggestion_details(state, proposal_id)

            except SuggestionWorkflowError:

                pass

        return {

            "confirmation_resolution": "suggestion_details",

            "confirmation_kind": "suggestion",

            "workflow_proposal_id": proposal_id,

            "awaiting_confirmation": True,

            "finished": True,

            "response": str(

                suggestion.get("detail_prompt")

                or "Tell me what you want to change in this follow-up."

            ),

        }



    return {

        "confirmation_resolution": "none",

    }





def _resume_document_confirmation(

    state: AgentState,

    pending: Dict[str, Any],

    decision: Optional[str],

    edit_kind: Optional[str],

) -> Dict[str, Any]:

    """Handle yes/no/edit for a persisted document proposal."""



    proposal_id = str(pending.get("proposal_id") or "")

    pending_document_id = pending.get("pending_document_id")

    pending_payload = pending.get("payload")

    uses_separated_approval = isinstance(pending_payload, dict)

    storage_choice = _parse_document_storage_choice(
        str(state.get("message") or "")
    )



    if edit_kind == "prompt" and decision is None:

        return {

            "confirmation_resolution": "edit_prompt",

            "confirmation_kind": "document",

            "workflow_proposal_id": proposal_id,

            "pending_document_id": pending_document_id,

            "awaiting_confirmation": True,

            "finished": True,

            "response": (

                "Sure. Tell me exactly what you want to change in the "

                "document proposal, for example: 'change the amount to "

                "500', 'remove action 2', or 'change the category to "

                "Utilities'."

            ),

        }



    if edit_kind == "detailed" and decision is None:

        return {

            "confirmation_resolution": "document_edit",

            "confirmation_kind": "document",

            "workflow_proposal_id": proposal_id,

            "editing_workflow_proposal_id": proposal_id,

            "pending_document_id": pending_document_id,

            "document_edit_request": str(state.get("message") or ""),

            "awaiting_confirmation": False,

            "finished": False,

            "response": "",

        }



    if storage_choice is not None and uses_separated_approval:

        try:

            approved = approve_document_interpretation(
                state,
                store_document=storage_choice,
            )

        except DocumentWorkflowError as exc:

            return {

                "confirmation_resolution": "edit_prompt",

                "confirmation_kind": "document",

                "workflow_proposal_id": proposal_id,

                "pending_document_id": pending_document_id,

                "awaiting_confirmation": True,

                "finished": True,

                "response": str(exc),

            }

        if approved.get("already_handled"):

            return {

                "confirmation_resolution": "document_already_handled",

                "confirmation_kind": "document",

                "workflow_proposal_id": approved.get("proposal_id"),

                "pending_document_id": pending_document_id,

                "awaiting_confirmation": False,

                "finished": True,

                "response": str(

                    approved.get("message")

                    or "This document interpretation was already verified."

                ),

            }

        return {

            "confirmation_resolution": "document_verified",

            "confirmation_kind": "document",

            "workflow_proposal_id": approved.get("proposal_id"),

            "pending_document_id": pending_document_id,

            "editing_workflow_proposal_id": None,

            "document_edit_request": None,

            "awaiting_confirmation": False,

            "finished": False,

            "response": "",

        }

    if decision == "yes" and uses_separated_approval:

        return {

            "confirmation_resolution": "edit_prompt",

            "confirmation_kind": "document",

            "workflow_proposal_id": proposal_id,

            "pending_document_id": pending_document_id,

            "awaiting_confirmation": True,

            "finished": True,

            "response": (

                "The interpretation can be verified, but I also need your "

                "storage choice. Reply 'verify and save' or "

                "'verify without saving'."

            ),

        }

    if decision == "yes":

        try:

            approved = approve_document_review(state)

        except DocumentWorkflowError as exc:

            return {

                "confirmation_resolution": "edit_prompt",

                "confirmation_kind": "document",

                "workflow_proposal_id": proposal_id,

                "pending_document_id": pending_document_id,

                "awaiting_confirmation": True,

                "finished": True,

                "response": str(exc),

            }



        if approved.get("already_handled"):

            return {

                "confirmation_resolution": "document_already_handled",

                "confirmation_kind": "document",

                "workflow_proposal_id": approved.get("proposal_id"),

                "pending_document_id": pending_document_id,

                "editing_workflow_proposal_id": None,

                "document_edit_request": None,

                "awaiting_confirmation": False,

                "finished": True,

                "response": str(

                    approved.get("message")

                    or "This document review was already approved."

                ),

            }



        return {

            "confirmation_resolution": "document_approved",

            "confirmation_kind": "document",

            "workflow_proposal_id": approved.get("proposal_id"),

            "pending_document_id": pending_document_id,

            "editing_workflow_proposal_id": None,

            "document_edit_request": None,

            "awaiting_confirmation": False,

            "finished": False,

            "response": "",

        }



    # NO / CANCEL

    try:

        rejected = reject_document_review(state)

    except DocumentWorkflowError:

        return {

            "confirmation_resolution": "error",

            "confirmation_kind": "document",

            "workflow_proposal_id": proposal_id,

            "awaiting_confirmation": False,

            "finished": True,

            "response": (

                "I couldn't safely update the pending document review. "

                "Please try again."

            ),

        }



    return {

        "confirmation_resolution": "document_rejected",

        "confirmation_kind": "document",

        "workflow_proposal_id": rejected.get("proposal_id"),

        "pending_document_id": pending_document_id,

        "editing_workflow_proposal_id": None,

        "document_edit_request": None,

        "awaiting_confirmation": False,

        "finished": True,

        "response": "Okay, I cancelled this document proposal.",

    }







def _resume_document_action_confirmation(

    state: AgentState,

    pending: Dict[str, Any],

    decision: Optional[str],

    edit_kind: Optional[str],

) -> Dict[str, Any]:

    """Handle the independent approval for document-derived actions."""

    proposal_id = str(pending.get("proposal_id") or "")

    pending_document_id = pending.get("pending_document_id")

    if edit_kind is not None and decision is None:

        return {

            "confirmation_resolution": "edit_prompt",

            "confirmation_kind": DOCUMENT_ACTION_KIND,

            "workflow_proposal_id": proposal_id,

            "pending_document_id": pending_document_id,

            "awaiting_confirmation": True,

            "finished": True,

            "response": (

                "These actions are separate from document verification. "

                "Reply yes to approve the exact actions or no to reject "

                "them. To change them, reject this review and upload or "

                "review a corrected interpretation."

            ),

        }

    if decision == "yes":

        try:

            approved = approve_document_action_review(state)

        except DocumentWorkflowError as exc:

            return {

                "confirmation_resolution": "error",

                "confirmation_kind": DOCUMENT_ACTION_KIND,

                "workflow_proposal_id": proposal_id,

                "pending_document_id": pending_document_id,

                "awaiting_confirmation": False,

                "finished": True,

                "response": str(exc),

            }

        if approved.get("already_handled"):

            return {

                "confirmation_resolution": "document_already_handled",

                "confirmation_kind": DOCUMENT_ACTION_KIND,

                "workflow_proposal_id": approved.get("proposal_id"),

                "pending_document_id": pending_document_id,

                "awaiting_confirmation": False,

                "finished": True,

                "response": str(

                    approved.get("message")

                    or "These document actions were already handled."

                ),

            }

        return {

            "confirmation_resolution": "document_actions_approved",

            "confirmation_kind": DOCUMENT_ACTION_KIND,

            "workflow_proposal_id": approved.get("proposal_id"),

            "pending_document_id": pending_document_id,

            "awaiting_confirmation": False,

            "finished": False,

            "response": "",

        }

    try:

        rejected = reject_document_action_review(state)

    except DocumentWorkflowError:

        return {

            "confirmation_resolution": "error",

            "confirmation_kind": DOCUMENT_ACTION_KIND,

            "workflow_proposal_id": proposal_id,

            "awaiting_confirmation": False,

            "finished": True,

            "response": (

                "I couldn't safely reject the derived actions. "

                "Please reload the current review and try again."

            ),

        }

    stored = bool(rejected.get("store_document"))

    return {

        "confirmation_resolution": "document_actions_rejected",

        "confirmation_kind": DOCUMENT_ACTION_KIND,

        "workflow_proposal_id": rejected.get("proposal_id"),

        "pending_document_id": pending_document_id,

        "awaiting_confirmation": False,

        "finished": True,

        "response": (

            "Okay, I rejected the derived actions. The stored document "

            "remains available."

            if stored

            else (

                "Okay, I rejected the derived actions. The original "

                "document was not stored."

            )

        ),

    }


def resume_confirmation_node(state: AgentState) -> Dict[str, Any]:

    """Resolve approval/rejection/edit before normal planning.



    Edits are never applied to the saved tool arguments directly.  Instead the

    exact pending proposal becomes trusted edit context and the request routes

    back through retrieval -> planner -> specialist -> duplicate/consistency

    checks -> review.  The revised action is then stored as revision N+1.

    """



    # File uploads must always enter the document-ingestion path. A pending
    # review must never consume the accompanying message or drop the file.
    if state.get("uploaded_file") is not None:

        return {

            "confirmation_resolution": "none",

        }



    key = _confirmation_key(state)



    if not key:

        return {

            "confirmation_resolution": "none",

        }



    message = str(state.get("message", ""))

    normalized_message = _normalize_reply(message)

    is_pure_workflow_control = normalized_message in (

        YES_RESPONSES

        | NO_RESPONSES

        | RETRY_RESPONSES

    )



    # If a prior request was approved and the process stopped before the

    # execution node completed, resume that exact durable revision before

    # planning a new request. ExecutionLedger makes completed action steps

    # replay-safe.

    try:

        resumable = find_resumable_document_execution(state)

    except Exception:

        resumable = None



    if resumable is not None:

        resumable_kind = str(

            resumable.get("kind") or "document"

        )

        return {

            "confirmation_resolution": "document_execute_resume",

            "confirmation_kind": resumable_kind,

            "workflow_proposal_id": resumable.get("proposal_id"),

            "pending_document_id": resumable.get("pending_document_id"),

            "continue_after_document_execution": bool(

                normalized_message

                and not is_pure_workflow_control

            ),

            "resumed_document_execution_summary": None,

            "awaiting_confirmation": False,

            "finished": False,

            "response": "",

        }



    if _normalize_reply(message) in RETRY_RESPONSES:

        try:

            retried = retry_failed_document_review(state)

        except DocumentWorkflowError as exc:

            return {

                "confirmation_resolution": "error",

                "confirmation_kind": "document",

                "awaiting_confirmation": False,

                "finished": True,

                "response": str(exc),

            }



        if retried.get("already_handled"):

            retried_kind = str(

                retried.get("kind") or "document"

            )

            return {

                "confirmation_resolution": "document_already_handled",

                "confirmation_kind": retried_kind,

                "workflow_proposal_id": retried.get("proposal_id"),

                "pending_document_id": retried.get("pending_document_id"),

                "awaiting_confirmation": False,

                "finished": True,

                "response": str(

                    retried.get("message")

                    or "This document retry was already handled."

                ),

            }



        retried_kind = str(

            retried.get("kind") or "document"

        )

        return {

            "confirmation_resolution": "document_retry_approved",

            "confirmation_kind": retried_kind,

            "workflow_proposal_id": retried.get("proposal_id"),

            "pending_document_id": retried.get("pending_document_id"),

            "awaiting_confirmation": False,

            "finished": False,

            "response": "",

        }

    decision = _parse_decision(message)

    storage_choice = _parse_document_storage_choice(message)

    edit_kind = _edit_request_kind(message)



    try:

        selected = _select_pending_workflow(state)

    except ConfirmationPersistenceError:

        selected = None



    if selected is None:

        return {

            "confirmation_resolution": "none",

        }



    routed_state = dict(state)

    routed_state["workflow_proposal_id"] = selected["proposal_id"]

    selected_kind = selected["kind"]



    if selected_kind == "document":

        if (

            decision is None

            and storage_choice is None

            and edit_kind is None

        ):

            return {

                "confirmation_resolution": "none",

            }



        try:

            document_pending = load_pending_document_review(routed_state)

        except DocumentWorkflowError:

            document_pending = None



        if document_pending is None:

            return {

                "confirmation_resolution": "none",

            }



        return _resume_document_confirmation(

            routed_state,

            document_pending,

            decision,

            edit_kind,

        )

    if selected_kind == DOCUMENT_ACTION_KIND:

        if decision is None and edit_kind is None:

            return {

                "confirmation_resolution": "none",

            }

        try:

            action_pending = load_pending_document_action_review(

                routed_state

            )

        except DocumentWorkflowError:

            action_pending = None

        if action_pending is None:

            return {

                "confirmation_resolution": "none",

            }

        return _resume_document_action_confirmation(

            routed_state,

            action_pending,

            decision,

            edit_kind,

        )



    if selected_kind == "suggestion":

        try:

            suggestion_pending = load_pending_suggestion(routed_state)

        except SuggestionWorkflowError:

            suggestion_pending = None



        if suggestion_pending is None:

            return {

                "confirmation_resolution": "none",

            }



        suggestion_payload = dict(

            suggestion_pending.get("payload") or {}

        )

        is_native_suggestion_payload = (

            suggestion_payload.get("kind") == "suggestion"

            and isinstance(

                suggestion_payload.get("suggestion"),

                dict,

            )

        )

        suggestion_stage = str(

            suggestion_payload.get("stage") or "offered"

        )



        if is_native_suggestion_payload:

            if (

                decision is None

                and edit_kind is None

                and suggestion_stage != "collecting_details"

            ):

                return {

                    "confirmation_resolution": "none",

                }



            return _resume_suggestion_confirmation(

                routed_state,

                suggestion_pending,

                decision,

                edit_kind,

            )

        # A revised suggestion is intentionally stored in the normal chat
        # payload shape. Let it continue through the exact chat approval path
        # below instead of treating the user's next reply as a new request.



    if decision is None and edit_kind is None:

        return {

            "confirmation_resolution": "none",

        }



    session = SessionLocal()



    try:

        proposal = _query_pending_proposal(

            session,

            routed_state,

            selected["proposal_id"],

        )



        if proposal is None:

            return {

                "confirmation_resolution": "none",

            }



        payload = _load_payload(proposal)



        actions = list(

            payload.get("planned_actions") or []

        )



        index = int(

            payload.get("current_action_index", 0) or 0

        )



        if edit_kind == "prompt" and decision is None:

            return {

                "confirmation_resolution": "edit_prompt",

                "workflow_proposal_id": str(proposal.proposal_id),

                "awaiting_confirmation": True,

                "finished": True,

                "response": (

                    "Sure. Tell me exactly what you want to change in "

                    "the pending action, for example: 'change the amount "

                    "to 500' or 'assign it to Meera'."

                ),

            }



        if edit_kind == "detailed" and decision is None:

            explicit_resolution = _explicit_duplicate_quantity_resolution(

                message,

                payload,

            )



            if explicit_resolution is not None:

                if explicit_resolution.get("mode") == "keep":

                    return _close_duplicate_as_keep_existing(

                        session=session,

                        proposal=proposal,

                        payload=payload,

                    )



                return _stage_explicit_duplicate_resolution_for_confirmation(

                    session=session,

                    proposal=proposal,

                    payload=payload,

                    state=state,

                    resolution=explicit_resolution,

                )



            pending_tool_call = payload.get("pending_tool_call")



            if not pending_tool_call:

                raise ConfirmationPersistenceError(

                    "The saved action cannot be edited because its tool call is missing."

                )



            current_action = None

            if 0 <= index < len(actions):

                maybe_action = actions[index]

                if isinstance(maybe_action, dict):

                    current_action = dict(maybe_action)



            edit_context: Dict[str, Any] = {

                "proposal_id": str(proposal.proposal_id),

                "revision": int(proposal.revision or 1),

                "confirmation_kind": payload.get("confirmation_kind") or proposal.kind,

                "current_action_index": index,

                "current_action": current_action,

                "pending_tool_call": pending_tool_call,

                "duplicate_status": payload.get("duplicate_status"),

                "duplicate_details": payload.get("duplicate_details"),

                "duplicate_match": payload.get("duplicate_match"),

            }



            return {

                "confirmation_resolution": "edit",

                "confirmation_kind": "action",

                "workflow_proposal_id": str(proposal.proposal_id),

                "editing_workflow_proposal_id": str(proposal.proposal_id),

                "pending_edit_context": edit_context,

                "force_action_review": True,

                "planned_actions": [],

                "current_action_index": 0,

                "pending_tool_call": None,

                "pending_ai_message": None,

                "awaiting_confirmation": False,

                "finished": False,

                "response": "",

            }



        if decision == "yes":

            duplicate_status = str(payload.get("duplicate_status") or "")

            duplicate_match = payload.get("duplicate_match")

            record_type = (

                str(duplicate_match.get("record_type") or "")

                if isinstance(duplicate_match, dict)

                else ""

            )



            if (

                duplicate_status == "CONFLICT"

                and record_type in {"grocery_item", "inventory_item"}

            ):

                return {

                    "confirmation_resolution": "edit_prompt",

                    "confirmation_kind": payload.get("confirmation_kind") or proposal.kind,

                    "workflow_proposal_id": str(proposal.proposal_id),

                    "awaiting_confirmation": True,

                    "finished": True,

                    "response": _quantity_conflict_resolution_prompt(payload),

                }



            pending_tool_call = payload.get("pending_tool_call")



            if not pending_tool_call:

                raise ConfirmationPersistenceError(

                    "The saved approval has no tool call."

                )



            pending_ai_message = _deserialize_ai_message(

                payload.get("pending_ai_message")

            )



            if pending_ai_message is None:

                raise ConfirmationPersistenceError(

                    "The saved approval has no tool-call message."

                )



            proposal.status = "APPROVED"

            proposal.approved_by = (

                str(state.get("user_id"))

                if state.get("user_id")

                else None

            )

            proposal.approved_at = utcnow()

            proposal.updated_at = utcnow()

            session.commit()



            return {

                "confirmation_resolution": "confirmed",

                "confirmation_kind": payload.get("confirmation_kind") or proposal.kind,

                "workflow_proposal_id": str(proposal.proposal_id),

                "editing_workflow_proposal_id": None,

                "pending_edit_context": None,

                "force_action_review": False,

                "planned_actions": actions,

                "current_action_index": index,

                "pending_tool_call": pending_tool_call,

                "pending_ai_message": pending_ai_message,

                "duplicate_status": payload.get("duplicate_status"),

                "duplicate_details": payload.get("duplicate_details"),

                "duplicate_match": payload.get("duplicate_match"),

                "awaiting_confirmation": False,

                "response": "",

                "finished": False,

            }



        # NO / CANCEL

        if index < len(actions):

            action = dict(actions[index])

            action["status"] = "cancelled"

            action["result"] = (

                "Cancelled because the user did not confirm the action."

            )

            actions[index] = action



        proposal.status = "REJECTED"

        proposal.updated_at = utcnow()

        session.commit()



        return {

            "confirmation_resolution": "cancelled",

            "confirmation_kind": payload.get("confirmation_kind") or proposal.kind,

            "workflow_proposal_id": str(proposal.proposal_id),

            "editing_workflow_proposal_id": None,

            "pending_edit_context": None,

            "force_action_review": False,

            "planned_actions": actions,

            "current_action_index": index,

            "pending_tool_call": None,

            "pending_ai_message": None,

            "awaiting_confirmation": False,

            "finished": True,

            "response": "Okay, I won't perform that action.",

        }



    except ConfirmationPersistenceError:

        session.rollback()



        return {

            "confirmation_resolution": "error",

            "awaiting_confirmation": False,

            "pending_tool_call": None,

            "pending_ai_message": None,

            "force_action_review": False,

            "finished": True,

            "response": (

                "I couldn't safely restore the pending review. "

                "Please submit the action again."

            ),

        }

    except Exception:

        session.rollback()



        return {

            "confirmation_resolution": "error",

            "awaiting_confirmation": False,

            "pending_tool_call": None,

            "pending_ai_message": None,

            "force_action_review": False,

            "finished": True,

            "response": (

                "I couldn't safely restore the pending review. "

                "Please submit the action again."

            ),

        }

    finally:

        session.close()





def route_after_resume(state: AgentState) -> str:

    """Route approval, cancellation, or edits without regenerating approvals."""



    resolution = state.get(

        "confirmation_resolution",

        "none",

    )



    if resolution == "confirmed":

        return "authorize"



    if resolution == "suggestion_confirmed":

        return "suggestion_authorize"



    if resolution in {

        "document_approved",

        "document_verified",

        "document_actions_approved",

        "document_execute_resume",

        "document_retry_approved",

    }:

        return "document_execute"



    if resolution in {"edit", "document_edit", "suggestion_replan"}:

        # Re-run retrieval before normal-action/document revision or an

        # accepted open-ended cross-domain follow-up.

        return "retrieve"



    if resolution in {

        "cancelled",

        "error",

        "edit_prompt",

        "revised_review",

        "suggestion_details",

        "document_rejected",

        "document_actions_rejected",

        "document_already_handled",

    }:

        return "save"



    return "retrieve"





def _quantity_conflict_resolution_prompt(payload: Dict[str, Any]) -> str:

    """Build a safe user-facing resolution prompt with no internal ids."""



    match = payload.get("duplicate_match") or {}

    call = payload.get("pending_tool_call") or {}

    args = call.get("args") or {}



    name = str(match.get("name") or args.get("name") or "this item")

    existing_quantity = match.get("quantity")

    existing_unit = _canonical_unit(match.get("unit"))

    requested_quantity = args.get("quantity")

    requested_unit = _canonical_unit(args.get("unit"))



    existing_text = str(existing_quantity)

    if existing_unit:

        existing_text += " " + existing_unit



    requested_text = str(requested_quantity)

    if requested_unit:

        requested_text += " " + requested_unit



    same_unit = (

        requested_unit is None

        or existing_unit is None

        or requested_unit == existing_unit

    )



    if same_unit:

        try:

            total = float(existing_quantity) + float(requested_quantity)

            total_text = (

                str(int(total)) if total.is_integer() else str(total)

            )

            if existing_unit or requested_unit:

                total_text += " " + str(existing_unit or requested_unit)



            return (

                "{0} is already on the list at {1}, while your new request "

                "mentions {2}. Would you like me to set it to {2}, add {2} "

                "more ({3} total), or keep it at {1}?\n"

                "Reply with something explicit such as 'set it to {2}', "

                "'add {2} more', or 'keep it'."

            ).format(name, existing_text, requested_text, total_text)

        except (TypeError, ValueError):

            pass



    return (

        "{0} already exists at {1}, while your new request mentions {2}. "

        "Tell me explicitly whether to set the existing quantity to {2}, "

        "keep the current quantity, or how you want the quantities combined."

    ).format(name, existing_text, requested_text)





def request_confirmation_node(state: AgentState) -> Dict[str, Any]:

    """Persist an exact normal-chat action, then offer approve/edit/cancel."""



    try:

        proposal_id = store_pending_confirmation(state)

    except ConfirmationPersistenceError:

        return {

            "workflow_proposal_id": None,

            "awaiting_confirmation": False,

            "finished": True,

            "response": (

                "I found an action that needs review, but I couldn't save "

                "the review safely. Please try again."

            ),

        }



    details = state.get("duplicate_details")



    duplicate_match = state.get("duplicate_match")

    record_type = (

        str(duplicate_match.get("record_type") or "")

        if isinstance(duplicate_match, dict)

        else ""

    )



    if (

        state.get("duplicate_status") == "CONFLICT"

        and record_type in {"grocery_item", "inventory_item"}

    ):

        payload = _build_confirmation_payload(state)

        return {

            "workflow_proposal_id": proposal_id,

            "confirmation_kind": state.get("confirmation_kind") or "conflict",

            "awaiting_confirmation": True,

            "finished": True,

            "response": _quantity_conflict_resolution_prompt(payload),

        }



    actions = list(state.get("planned_actions") or [])

    index = int(state.get("current_action_index", 0) or 0)

    action_description = "the pending action"



    if 0 <= index < len(actions):

        current = actions[index]

        if isinstance(current, dict):

            action_description = str(

                current.get("description")

                or current.get("intent")

                or action_description

            )



    parts = []

    if details:

        parts.append(str(details))



    if state.get("confirmation_kind") == "suggestion":

        parts.append(

            "Follow-up action for review: {0}".format(action_description)

        )

    elif state.get("editing_workflow_proposal_id"):

        parts.append(

            "Revised action: {0}".format(action_description)

        )

    else:

        parts.append(

            "Action for review: {0}".format(action_description)

        )



    parts.append(

        "Reply yes to approve, no to cancel, or tell me what you want to change."

    )



    return {

        "workflow_proposal_id": proposal_id,

        "confirmation_kind": (

            state.get("confirmation_kind")

            or "action"

        ),

        "awaiting_confirmation": True,

        "finished": True,

        "response": "\n".join(parts),

    }
