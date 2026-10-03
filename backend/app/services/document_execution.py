"""Durable, idempotent execution for approved document proposals.
Step 8B of the AI Home Manager production refactor.
The model never executes these mutations.  This module loads the exact
approved proposal revision from the database, rechecks authorization and
fresh conflicts, archives the original document, and applies each approved
operation with a ledger row in the same database transaction as the domain
write.
Compatibility target: Python 3.8+.
"""
from __future__ import annotations
import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.exc import IntegrityError

from app.ai.agents.permissions import is_authorized
from app.db.base import SessionLocal, utcnow
from app.models.documents import Document, DocumentLink, PendingDocumentUpload
from app.models.enums import (
    DocumentType,
    IssueStatus,
    MembershipStatus,
    Priority,
    TaskStatus,
)
from app.models.finance import Expense, RecurringBill
from app.models.inventory import GroceryItem, InventoryItem
from app.models.maintenance import Appliance, MaintenanceIssue, Repair
from app.models.people import Membership, User
from app.models.tasks import CalendarEvent, Task
from app.models.workflows import ExecutionLedger, WorkflowProposal
from app.services.document_lifecycle import (
    PENDING_DOCUMENT_TTL_HOURS,
    cleanup_terminal_pending_upload,
)
from app.services.document_workflow import (
    DOCUMENT_ACTION_KIND,
    DOCUMENT_REVIEW_KIND,
    persist_document_action_review,
)
from app.rag.document_index import index_document_best_effort
from app.storage.cloudinary_storage import upload_file
from app.storage.temp_storage import delete_temp_file


class DocumentExecutionError(RuntimeError):
    """Raised when approved document execution cannot continue safely."""


_ARCHIVE_ACTION_INDEX = -1
_ARCHIVE_OPERATION = "__archive_document__"
_EXECUTION_STALE_AFTER = timedelta(
    minutes=15
)
_ACTION_STALE_AFTER = timedelta(
    minutes=15
)


def _json_default(value: Any) -> str:
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _required_execution_scope_value(
    state: Dict[str, Any],
    field: str,
    max_length: int,
) -> str:
    """Read one required execution-scope value."""
    value = state.get(field)
    if value is None or not isinstance(value, str):
        raise DocumentExecutionError(
            "{} is required for document execution.".format(
                field
            )
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
        raise DocumentExecutionError(
            "{} has an invalid value.".format(field)
        )
    return cleaned


def _execution_scope(
    state: Dict[str, Any],
) -> Tuple[str, str, str]:
    """Return required user, conversation, and session IDs."""
    return (
        _required_execution_scope_value(
            state,
            "user_id",
            36,
        ),
        _required_execution_scope_value(
            state,
            "conversation_id",
            36,
        ),
        _required_execution_scope_value(
            state,
            "session_id",
            100,
        ),
    )


def _query_execution_row(
    session,
    state: Dict[str, Any],
) -> Optional[WorkflowProposal]:
    """Find an executable proposal inside the exact owned scope."""
    (
        user_id,
        conversation_id,
        session_id,
    ) = _execution_scope(state)
    proposal_id_value = state.get(
        "workflow_proposal_id"
    )
    if proposal_id_value is None:
        proposal_id = ""
    elif isinstance(
        proposal_id_value,
        str,
    ):
        proposal_id = (
            proposal_id_value.strip()
        )
    else:
        raise DocumentExecutionError(
            "workflow_proposal_id has an invalid value."
        )
    query = (
        session.query(
            WorkflowProposal
        )
        .filter(
            WorkflowProposal.user_id
            == user_id,
            WorkflowProposal.conversation_id
            == conversation_id,
            WorkflowProposal.session_id
            == session_id,
            WorkflowProposal.kind.in_(
                (
                    DOCUMENT_REVIEW_KIND,
                    DOCUMENT_ACTION_KIND,
                )
            ),
            WorkflowProposal.status.in_(
                (
                    "APPROVED",
                    "EXECUTING",
                )
            ),
        )
    )
    if proposal_id:
        query = query.filter(
            WorkflowProposal.proposal_id
            == proposal_id
        )
    return (
        query.order_by(
            desc(
                WorkflowProposal.updated_at
            ),
            desc(
                WorkflowProposal.created_at
            ),
        )
        .first()
    )


def _comparable_datetime(
    value: datetime,
    reference: datetime,
) -> datetime:
    """Make reference timezone-compatible with a stored datetime."""
    if (
        value.tzinfo is None
        and reference.tzinfo is not None
    ):
        return reference.replace(
            tzinfo=None
        )
    if (
        value.tzinfo is not None
        and reference.tzinfo is None
    ):
        return reference.replace(
            tzinfo=value.tzinfo
        )
    return reference


def _execution_is_stale(
    row: WorkflowProposal,
    now: Optional[datetime] = None,
) -> bool:
    """Return whether an EXECUTING claim is old enough to recover."""
    if row.status != "EXECUTING":
        return False
    if row.updated_at is None:
        return True
    now = now or utcnow()
    comparable_now = _comparable_datetime(
        row.updated_at,
        now,
    )
    return (
        row.updated_at
        <= comparable_now
        - _EXECUTION_STALE_AFTER
    )


def _claim_document_execution(
    session,
    row: WorkflowProposal,
    state: Dict[str, Any],
) -> None:
    """Atomically claim APPROVED or stale EXECUTING work."""
    (
        user_id,
        conversation_id,
        session_id,
    ) = _execution_scope(state)
    proposal_id = str(
        row.proposal_id
    )
    revision = int(
        row.revision or 1
    )
    args_hash = str(
        row.args_hash
    )
    pending_id = str(
        row.pending_document_id or ""
    )
    current_status = str(
        row.status or ""
    )
    observed_updated_at = (
        row.updated_at
    )
    now = utcnow()
    proposal_kind = str(row.kind or "")
    if proposal_kind not in {
        DOCUMENT_REVIEW_KIND,
        DOCUMENT_ACTION_KIND,
    }:
        raise DocumentExecutionError(
            "The document proposal has an invalid workflow kind."
        )

    query = (
        session.query(
            WorkflowProposal
        )
        .filter(
            WorkflowProposal.proposal_id
            == proposal_id,
            WorkflowProposal.user_id
            == user_id,
            WorkflowProposal.conversation_id
            == conversation_id,
            WorkflowProposal.session_id
            == session_id,
            WorkflowProposal.kind
            == proposal_kind,
            WorkflowProposal.revision
            == revision,
            WorkflowProposal.args_hash
            == args_hash,
            WorkflowProposal.pending_document_id
            == pending_id,
            WorkflowProposal.approved_by
            == user_id,
        )
    )
    if current_status == "APPROVED":
        query = query.filter(
            WorkflowProposal.status
            == "APPROVED"
        )
    elif current_status == "EXECUTING":
        if not _execution_is_stale(
            row,
            now=now,
        ):
            raise DocumentExecutionError(
                "This document execution is already "
                "in progress."
            )
        query = query.filter(
            WorkflowProposal.status
            == "EXECUTING",
            WorkflowProposal.updated_at
            == observed_updated_at,
        )
    else:
        raise DocumentExecutionError(
            "The document proposal is not ready "
            "for execution."
        )
    changed = query.update(
        {
            WorkflowProposal.status: (
                "EXECUTING"
            ),
            WorkflowProposal.updated_at: (
                now
            ),
            WorkflowProposal.last_error: (
                None
            ),
        },
        synchronize_session=False,
    )
    if changed != 1:
        session.rollback()
        raise DocumentExecutionError(
            "This document execution was claimed "
            "by another request."
        )
    session.commit()
    session.refresh(row)


def _load_payload(row: WorkflowProposal) -> Dict[str, Any]:
    try:
        payload = json.loads(row.payload_json)
    except Exception as exc:
        raise DocumentExecutionError(
            "The approved document proposal is unreadable."
        ) from exc
    if not isinstance(payload, dict):
        raise DocumentExecutionError(
            "The approved document proposal has an invalid payload."
        )
    if _hash_json(payload) != row.args_hash:
        raise DocumentExecutionError(
            "The approved document proposal failed its integrity check."
        )
    return payload


def find_resumable_document_execution(
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Find approved work or stale interrupted execution.
    A recently EXECUTING proposal belongs to an active request and is not
    returned for concurrent resumption.
    """
    session = SessionLocal()
    try:
        row = _query_execution_row(
            session,
            state,
        )
        if row is None:
            return None
        if (
            row.status == "EXECUTING"
            and not _execution_is_stale(
                row
            )
        ):
            return None
        return {
            "proposal_id": str(
                row.proposal_id
            ),
            "kind": str(
                row.kind
            ),
            "revision": int(
                row.revision or 1
            ),
            "pending_document_id": (
                row.pending_document_id
            ),
            "status": row.status,
        }
    finally:
        session.close()


def _parse_datetime(value: Any, field_name: str) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise DocumentExecutionError(
            "Invalid {0}; use an ISO datetime.".format(field_name)
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_date(value: Any, field_name: str) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise DocumentExecutionError(
            "Invalid {0}; use YYYY-MM-DD.".format(field_name)
        ) from exc


def _parse_priority(value: Any) -> Priority:
    raw = str(value or Priority.NORMAL.value).strip()
    for candidate in Priority:
        if candidate.value.casefold() == raw.casefold():
            return candidate
    raise DocumentExecutionError(
        "Invalid priority '{0}'.".format(raw)
    )


def _document_type_from_values(
    classified_type: Optional[str],
    proposal_type: Optional[str],
) -> DocumentType:
    haystack = "{0} {1}".format(
        classified_type or "",
        proposal_type or "",
    ).casefold()
    if "receipt" in haystack:
        return DocumentType.RECEIPT
    if "bill" in haystack or "invoice" in haystack:
        return DocumentType.BILL
    if "warranty" in haystack:
        return DocumentType.WARRANTY
    return DocumentType.OTHER


def _resolve_active_user(session, reference: Any) -> Optional[str]:
    if reference is None or str(reference).strip() == "":
        return None
    value = str(reference).strip()
    by_id = (
        session.query(User)
        .join(Membership)
        .filter(
            User.user_id == value,
            Membership.status == MembershipStatus.ACTIVE,
        )
        .first()
    )
    if by_id is not None:
        return str(by_id.user_id)
    matches = (
        session.query(User)
        .join(Membership)
        .filter(
            func.lower(User.display_name) == value.casefold(),
            Membership.status == MembershipStatus.ACTIVE,
        )
        .all()
    )
    if len(matches) == 1:
        return str(matches[0].user_id)
    if not matches:
        raise DocumentExecutionError(
            "No active household member matches '{0}'.".format(value)
        )
    raise DocumentExecutionError(
        "More than one active household member matches '{0}'.".format(value)
    )


def _resolve_appliance(session, reference: Any) -> Optional[str]:
    if reference is None or str(reference).strip() == "":
        return None
    value = str(reference).strip()
    row = session.query(Appliance).filter(
        Appliance.appliance_id == value
    ).first()
    if row is not None:
        return str(row.appliance_id)
    matches = session.query(Appliance).filter(
        func.lower(Appliance.name) == value.casefold()
    ).all()
    if len(matches) == 1:
        return str(matches[0].appliance_id)
    if not matches:
        raise DocumentExecutionError(
            "No appliance matches '{0}'.".format(value)
        )
    raise DocumentExecutionError(
        "More than one appliance matches '{0}'.".format(value)
    )


def _ledger_key(
    proposal_id: str,
    revision: int,
    action_index: int,
    operation: str,
    arguments: Dict[str, Any],
) -> str:
    material = {
        "proposal_id": proposal_id,
        "revision": revision,
        "action_index": action_index,
        "operation": operation,
        "arguments": arguments,
    }
    return _hash_json(material)


def _read_ledger_result(row: ExecutionLedger) -> Dict[str, Any]:
    if not row.result_json:
        return {}
    try:
        result = json.loads(row.result_json)
    except Exception:
        return {}
    return result if isinstance(result, dict) else {}


def _preflight_action(
    session,
    action: Dict[str, Any],
    role: str,
) -> List[str]:
    """Fresh permission and obvious duplicate/conflict checks.
    This is intentionally conservative.  Step 10 will move these rules into
    the shared consistency service used by both chat and document flows.
    """
    errors: List[str] = []
    domain = str(action.get("domain") or "").strip().lower()
    operation = str(action.get("operation") or "").strip()
    arguments = dict(action.get("arguments") or {})
    if action.get("blocked"):
        errors.append(
            str(action.get("blocked_reason") or "Action is blocked.")
        )
        return errors
    entity_references = [
        str(item).strip()
        for item in (action.get("entity_references") or [])
        if str(item).strip()
    ]
    if entity_references:
        errors.append(
            "Resolve household references before execution: {0}.".format(
                ", ".join(entity_references)
            )
        )
    if not is_authorized(role, domain, operation):
        errors.append(
            "The current role is not authorized to execute '{0}' in {1}.".format(
                operation or "(unknown)",
                domain or "(unknown domain)",
            )
        )
        return errors
    if operation == "log_expense":
        try:
            amount = int(arguments.get("amount_minor"))
        except (TypeError, ValueError):
            errors.append("Expense amount is invalid.")
            amount = None
        occurred_at = _parse_datetime(
            arguments.get("occurred_at"),
            "occurred_at",
        )
        currency = str(arguments.get("currency") or "").upper().strip()
        category = str(arguments.get("category") or "").strip()
        if amount is not None and occurred_at is not None and category:
            existing = session.query(Expense).filter(
                Expense.amount_minor == amount,
                Expense.currency == currency,
                func.lower(Expense.category) == category.casefold(),
                Expense.occurred_at == occurred_at,
            ).first()
            if existing is not None:
                errors.append(
                    "A matching expense already exists for the same amount, category, currency, and time."
                )
    elif operation == "add_grocery_item":
        name = str(arguments.get("name") or "").strip()
        if name:
            existing = session.query(GroceryItem).filter(
                func.lower(GroceryItem.name) == name.casefold(),
                GroceryItem.purchased.is_(False),
            ).first()
            if existing is not None:
                errors.append(
                    "An unpurchased grocery item named '{0}' already exists.".format(
                        name
                    )
                )
    elif operation == "add_inventory_item":
        name = str(arguments.get("name") or "").strip()
        if name:
            existing = session.query(InventoryItem).filter(
                func.lower(InventoryItem.name) == name.casefold()
            ).first()
            if existing is not None:
                errors.append(
                    "Inventory already contains an item named '{0}'.".format(name)
                )
    elif operation == "create_recurring_bill":
        payee = str(arguments.get("payee") or "").strip()
        due_at = _parse_datetime(arguments.get("due_at"), "due_at")
        if payee and due_at is not None:
            existing = session.query(RecurringBill).filter(
                func.lower(RecurringBill.payee) == payee.casefold(),
                RecurringBill.due_at == due_at,
            ).first()
            if existing is not None:
                errors.append(
                    "A recurring bill for '{0}' with the same due time already exists.".format(
                        payee
                    )
                )
    elif operation == "create_task":
        title = str(arguments.get("title") or "").strip()
        due_at = _parse_datetime(arguments.get("due_at"), "due_at")
        assigned_to = _resolve_active_user(
            session,
            arguments.get("assigned_to"),
        )
        query = session.query(Task).filter(
            func.lower(Task.title) == title.casefold(),
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
        )
        if due_at is not None:
            query = query.filter(Task.due_at == due_at)
        if assigned_to is not None:
            query = query.filter(Task.assigned_to == assigned_to)
        if title and query.first() is not None:
            errors.append(
                "A matching open household task already exists."
            )
    elif operation == "create_calendar_event":
        starts_at = _parse_datetime(arguments.get("starts_at"), "starts_at")
        ends_at = _parse_datetime(arguments.get("ends_at"), "ends_at")
        if starts_at is not None and ends_at is not None:
            if ends_at <= starts_at:
                errors.append("Calendar event end time must be after start time.")
            else:
                conflict = session.query(CalendarEvent).filter(
                    CalendarEvent.starts_at < ends_at,
                    CalendarEvent.ends_at > starts_at,
                ).first()
                if conflict is not None:
                    errors.append(
                        "The proposed calendar event overlaps an existing event."
                    )
    elif operation == "add_appliance":
        name = str(arguments.get("name") or "").strip()
        brand = str(arguments.get("brand") or "").strip()
        model = str(arguments.get("model") or "").strip()
        query = session.query(Appliance).filter(
            func.lower(Appliance.name) == name.casefold()
        )
        if brand:
            query = query.filter(
                func.lower(func.coalesce(Appliance.brand, "")) == brand.casefold()
            )
        if model:
            query = query.filter(
                func.lower(func.coalesce(Appliance.model, "")) == model.casefold()
            )
        if name and query.first() is not None:
            errors.append("A matching appliance already exists.")
    elif operation == "report_issue":
        description = str(arguments.get("description") or "").strip()
        appliance_id = _resolve_appliance(
            session,
            arguments.get("appliance_id"),
        )
        query = session.query(MaintenanceIssue).filter(
            func.lower(MaintenanceIssue.description) == description.casefold(),
            MaintenanceIssue.status.in_([
                IssueStatus.OPEN,
                IssueStatus.IN_PROGRESS,
            ]),
        )
        if appliance_id is not None:
            query = query.filter(
                MaintenanceIssue.appliance_id == appliance_id
            )
        if description and query.first() is not None:
            errors.append("A matching open maintenance issue already exists.")
    elif operation == "log_repair":
        appliance_id = _resolve_appliance(
            session,
            arguments.get("appliance_id"),
        )
        serviced_at = _parse_date(
            arguments.get("serviced_at"),
            "serviced_at",
        ) or date.today()
        provider = str(arguments.get("provider") or "").strip()
        query = session.query(Repair).filter(
            Repair.serviced_at == serviced_at
        )
        if appliance_id is not None:
            query = query.filter(Repair.appliance_id == appliance_id)
        if provider:
            query = query.filter(
                func.lower(func.coalesce(Repair.provider, ""))
                == provider.casefold()
            )
        if query.first() is not None:
            errors.append("A matching repair record already exists.")
    # Expense duplicates are intentionally handled by the shared consistency
    # service in the next step.  The new document_id does not exist until this
    # exact execution, so a document-key check here would not be meaningful.
    return errors


def _completed_action_matches_ledger(
    session,
    proposal: WorkflowProposal,
    action_index: int,
    action: Dict[str, Any],
) -> bool:
    """Return true only for the exact completed action of this revision."""

    operation = str(action.get("operation") or "").strip()
    arguments = dict(action.get("arguments") or {})
    expected_key = _ledger_key(
        str(proposal.proposal_id),
        int(proposal.revision),
        action_index,
        operation,
        arguments,
    )
    arguments_json = _canonical_json(arguments)
    ledger = session.query(ExecutionLedger).filter(
        ExecutionLedger.proposal_id == str(proposal.proposal_id),
        ExecutionLedger.revision == int(proposal.revision),
        ExecutionLedger.action_index == action_index,
    ).first()

    if ledger is not None:
        if str(ledger.idempotency_key or "") != expected_key:
            raise DocumentExecutionError(
                "Stored execution arguments do not match the approved revision."
            )
        if str(ledger.status or "") == "COMPLETED":
            return True

    prior_completed = session.query(ExecutionLedger).filter(
        ExecutionLedger.proposal_id == str(proposal.proposal_id),
        ExecutionLedger.revision < int(proposal.revision),
        ExecutionLedger.action_index == action_index,
        ExecutionLedger.status == "COMPLETED",
    ).order_by(
        ExecutionLedger.revision.desc()
    ).first()

    if prior_completed is None:
        return False

    if (
        str(prior_completed.operation or "") != operation
        or str(prior_completed.arguments_json or "") != arguments_json
    ):
        raise DocumentExecutionError(
            "An action at this position already completed in an earlier "
            "revision and cannot be changed or executed again."
        )

    return True


def _return_to_review(
    row: WorkflowProposal,
    payload: Dict[str, Any],
    failures: List[Dict[str, Any]],
    completed_action_indexes: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Invalidate stale approval and create a new blocked review revision."""
    proposal = dict(payload.get("document_proposal") or {})
    actions = [
        dict(action or {})
        for action in (proposal.get("actions") or [])
    ]
    warnings = list(proposal.get("warnings") or [])
    completed_revision = int(row.revision or 1)
    for index in completed_action_indexes or []:
        if 0 <= index < len(actions):
            action = actions[index]
            action["blocked"] = True
            action["execution_status"] = "completed"
            action["completed_revision"] = completed_revision
            action["blocked_reason"] = (
                "Already completed under approved revision {0}; this action "
                "will not be executed again."
            ).format(completed_revision)
            actions[index] = action
    for failure in failures:
        index = int(failure.get("action_index", -1))
        reasons = [
            str(reason)
            for reason in (failure.get("reasons") or [])
            if str(reason).strip()
        ]
        if not reasons:
            continue
        warning = "Execution freshness check: {0}".format(" ".join(reasons))
        if warning not in warnings:
            warnings.append(warning)
        if 0 <= index < len(actions):
            action = actions[index]
            action["blocked"] = True
            existing = str(action.get("blocked_reason") or "").strip()
            combined = " ".join(reasons)
            action["blocked_reason"] = (
                (existing + " " + combined).strip()
                if existing
                else combined
            )
            actions[index] = action
    proposal["actions"] = actions
    proposal["warnings"] = warnings
    proposal["clarification_required"] = True
    if not proposal.get("clarification_question"):
        proposal["clarification_question"] = (
            "The household changed or a conflict was found after approval. "
            "Please edit the affected action before approving again."
        )
    payload["document_proposal"] = proposal
    payload["requires_clarification"] = True
    payload["execution_preflight_errors"] = failures
    review_payload = payload.get("review_payload")
    if isinstance(review_payload, dict):
        review_payload["proposal"] = proposal
        payload["review_payload"] = review_payload
    now = utcnow()
    row.revision = int(row.revision or 0) + 1
    row.payload_json = _canonical_json(payload)
    row.args_hash = _hash_json(payload)
    row.status = "AWAITING_REVIEW"
    row.approved_by = None
    row.approved_at = None
    row.updated_at = now
    row.expires_at = now + timedelta(
        hours=PENDING_DOCUMENT_TTL_HOURS
    )
    row.last_error = "Fresh execution checks require another review."
    return {
        "proposal_id": str(row.proposal_id),
        "revision": int(row.revision),
        "payload": payload,
    }


def _validated_archive_result(
    result: Dict[str, Any],
    uploaded_by: str,
) -> Tuple[str, Dict[str, Any]]:
    """Validate that a completed archive ledger points to an owned document."""

    document_id = str(result.get("document_id") or "").strip()
    if not document_id:
        raise DocumentExecutionError(
            "The completed archive record is missing its document."
        )

    session = SessionLocal()
    try:
        document = session.query(Document).filter(
            Document.document_id == document_id,
            Document.uploaded_by == uploaded_by,
            Document.status == "approved",
        ).first()
        if document is None:
            raise DocumentExecutionError(
                "The completed archive document is unavailable."
            )
    finally:
        session.close()

    # A replay may be the first request after an earlier embedding outage or
    # process interruption. Stable chunk ids and upsert semantics make this
    # repair safe and idempotent. Archive validity never depends on Chroma.
    index_result = index_document_best_effort(
        document_id=document_id,
        user_id=uploaded_by,
    )
    replay_result = dict(result)
    replay_result["indexed"] = bool(
        index_result.get("indexed")
    )

    return document_id, replay_result


def _archive_original(
    proposal: WorkflowProposal,
    pending: PendingDocumentUpload,
    payload: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Archive the staged original under one durable ledger claim."""

    archive_arguments = {
        "pending_document_id": str(pending.pending_id),
    }
    key = _ledger_key(
        str(proposal.proposal_id),
        int(proposal.revision),
        _ARCHIVE_ACTION_INDEX,
        _ARCHIVE_OPERATION,
        archive_arguments,
    )
    execution_id, replayed, claim_time = _claim_action_execution(
        proposal,
        _ARCHIVE_ACTION_INDEX,
        _ARCHIVE_OPERATION,
        archive_arguments,
        key,
    )

    uploaded_by = str(pending.uploaded_by or "").strip()
    if not uploaded_by:
        raise DocumentExecutionError(
            "The staged document has no owner."
        )

    if replayed is not None:
        return _validated_archive_result(replayed, uploaded_by)

    if claim_time is None:
        raise DocumentExecutionError(
            "The archive claim is invalid."
        )

    temp_path = str(pending.temp_path or "").strip()
    session = SessionLocal()

    try:
        if not temp_path or not os.path.exists(temp_path):
            raise DocumentExecutionError(
                "The staged original file is no longer available."
            )

        deterministic_public_id = "document_{0}".format(
            pending.pending_id
        )
        cloud_result = upload_file(
            temp_path,
            public_id=deterministic_public_id,
            overwrite=True,
        )

        if not isinstance(cloud_result, dict):
            raise DocumentExecutionError(
                "Permanent storage returned an invalid response."
            )

        public_id = str(
            cloud_result.get("public_id") or ""
        ).strip()
        if not public_id:
            raise DocumentExecutionError(
                "Permanent storage did not return a document key."
            )

        document_proposal = payload.get("document_proposal") or {}
        document = Document(
            document_type=_document_type_from_values(
                pending.classified_document_type,
                document_proposal.get("document_type"),
            ),
            classified_document_type=pending.classified_document_type,
            domain=pending.domain,
            classification_confidence=pending.classification_confidence,
            classification_reason=pending.classification_reason,
            storage_key=public_id,
            original_filename=pending.original_filename,
            mime_type=pending.mime_type,
            extension=pending.extension,
            file_size=(
                cloud_result.get("bytes")
                or pending.file_size
            ),
            sha256=pending.sha256,
            normalized_text_hash=pending.normalized_text_hash,
            visual_hashes_json=pending.visual_hashes_json,
            extracted_text=pending.extracted_text,
            extraction_method=pending.extraction_method,
            page_count=pending.page_count,
            prompt_injection_detected=bool(
                pending.prompt_injection_detected
            ),
            status="approved",
            uploaded_by=uploaded_by,
        )
        session.add(document)
        session.flush()

        result = {
            "document_id": str(document.document_id),
            "public_id": public_id,
            "resource_type": cloud_result.get("resource_type"),
            "format": cloud_result.get("format"),
            "asset_id": cloud_result.get("asset_id"),
            "replayed": False,
        }
        completed_at = utcnow()

        changed = session.query(ExecutionLedger).filter(
            ExecutionLedger.execution_id == execution_id,
            ExecutionLedger.idempotency_key == key,
            ExecutionLedger.status == "RUNNING",
            ExecutionLedger.updated_at == claim_time,
        ).update(
            {
                ExecutionLedger.status: "COMPLETED",
                ExecutionLedger.result_json: _canonical_json(result),
                ExecutionLedger.error_message: None,
                ExecutionLedger.completed_at: completed_at,
                ExecutionLedger.updated_at: completed_at,
            },
            synchronize_session=False,
        )

        if changed != 1:
            raise DocumentExecutionError(
                "The archive claim is no longer owned by this request."
            )

        db_pending = session.query(PendingDocumentUpload).filter(
            PendingDocumentUpload.pending_id == pending.pending_id,
            PendingDocumentUpload.uploaded_by == uploaded_by,
        ).first()
        if db_pending is None:
            raise DocumentExecutionError(
                "The staged document is unavailable."
            )
        db_pending.status = "archived_pending_actions"

        # Document metadata, pending lifecycle, and archive-ledger completion
        # become visible atomically.
        session.commit()

        try:
            delete_temp_file(temp_path)
        except Exception:
            # The permanent archive and database metadata are authoritative.
            pass

        # Chroma is a replaceable semantic index, not the source of truth.
        # Index only after the archive/ledger transaction has committed. A
        # failure is logged by the best-effort wrapper and repaired by replay
        # or the reindex command without invalidating the stored document.
        index_result = index_document_best_effort(
            document_id=str(document.document_id),
            user_id=uploaded_by,
        )
        result["indexed"] = bool(
            index_result.get("indexed")
        )

        return str(document.document_id), result

    except Exception as exc:
        session.rollback()
        replayed_after_failure = _record_action_failure(
            execution_id,
            key,
            claim_time,
            exc,
        )

        if replayed_after_failure is not None:
            return _validated_archive_result(
                replayed_after_failure,
                uploaded_by,
            )

        # Never delete the deterministic object here. Another request may
        # have recovered the same archive claim and now own that object key.
        # A retry safely overwrites the same key, and lifecycle cleanup can
        # remove an unreferenced object after terminal failure.
        if isinstance(exc, DocumentExecutionError):
            raise

        raise DocumentExecutionError(
            "Unable to archive the approved original document."
        ) from exc

    finally:
        session.close()


def _finalize_verified_interpretation(
    proposal: WorkflowProposal,
    pending: PendingDocumentUpload,
    payload: Dict[str, Any],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Finalize storage choice, then create a separate action review."""

    decision = payload.get("document_decision") or {}
    if (
        not isinstance(decision, dict)
        or decision.get("interpretation_verified") is not True
        or not isinstance(decision.get("store_document"), bool)
    ):
        raise DocumentExecutionError(
            "The approved document decision is invalid."
        )

    store_document = bool(decision["store_document"])
    document_id: Optional[str] = None
    archive_result: Dict[str, Any] = {
        "stored": False,
        "reason": "storage_declined",
    }

    try:
        if store_document:
            document_id, archive_result = _archive_original(
                proposal,
                pending,
                payload,
            )
            archive_result = dict(archive_result)
            archive_result["stored"] = True

        session = SessionLocal()
        try:
            changed = session.query(WorkflowProposal).filter(
                WorkflowProposal.proposal_id == proposal.proposal_id,
                WorkflowProposal.user_id == proposal.user_id,
                WorkflowProposal.conversation_id
                == proposal.conversation_id,
                WorkflowProposal.session_id == proposal.session_id,
                WorkflowProposal.kind == DOCUMENT_REVIEW_KIND,
                WorkflowProposal.status == "EXECUTING",
                WorkflowProposal.revision == proposal.revision,
                WorkflowProposal.args_hash == proposal.args_hash,
                WorkflowProposal.approved_by == proposal.approved_by,
            ).update(
                {
                    WorkflowProposal.status: "COMPLETED",
                    WorkflowProposal.updated_at: utcnow(),
                    WorkflowProposal.last_error: None,
                },
                synchronize_session=False,
            )
            if changed != 1:
                session.rollback()
                current = session.get(
                    WorkflowProposal,
                    str(proposal.proposal_id),
                )
                if current is None or current.status != "COMPLETED":
                    raise DocumentExecutionError(
                        "The verified document finalization changed "
                        "before completion."
                    )
            else:
                session.commit()
        finally:
            session.close()

        action_review = persist_document_action_review(
            state,
            source_proposal_id=str(proposal.proposal_id),
            document_id=document_id,
        )

        storage_message = (
            "The original document was stored securely."
            if store_document
            else "The original document was not stored, as requested."
        )

        if action_review.get("created"):
            return {
                "status": "ACTION_REVIEW_REQUIRED",
                "confirmation_kind": DOCUMENT_ACTION_KIND,
                "proposal_id": str(proposal.proposal_id),
                "revision": int(proposal.revision),
                "pending_document_id": str(proposal.pending_document_id),
                "document_id": document_id,
                "archive": archive_result,
                "action_proposal_id": action_review.get("proposal_id"),
                "action_revision": action_review.get("revision"),
                "action_args_hash": action_review.get("args_hash"),
                "action_payload": action_review.get("payload"),
                "execution_results": [],
                "response": (
                    "The document interpretation is verified. "
                    + storage_message
                    + " The derived actions have not run. Review them "
                    "separately, then reply yes to approve or no to reject."
                ),
            }

        return {
            "status": "COMPLETED",
            "proposal_id": str(proposal.proposal_id),
            "revision": int(proposal.revision),
            "pending_document_id": str(proposal.pending_document_id),
            "document_id": document_id,
            "archive": archive_result,
            "execution_results": [],
            "response": (
                "The document interpretation is verified. "
                + storage_message
                + " There were no executable derived actions."
            ),
        }

    except Exception as exc:
        failure_session = SessionLocal()
        try:
            row = failure_session.get(
                WorkflowProposal,
                str(proposal.proposal_id),
            )
            if row is not None and row.status in {"EXECUTING", "COMPLETED"}:
                row.status = "FAILED"
                row.updated_at = utcnow()
                row.last_error = str(exc)
            failed_pending = failure_session.get(
                PendingDocumentUpload,
                str(proposal.pending_document_id),
            )
            if failed_pending is not None:
                failed_pending.status = "execution_failed"
            failure_session.commit()
        finally:
            failure_session.close()

        return {
            "status": "FAILED",
            "proposal_id": str(proposal.proposal_id),
            "revision": int(proposal.revision),
            "pending_document_id": str(proposal.pending_document_id),
            "document_id": document_id,
            "archive": archive_result,
            "execution_results": [],
            "response": (
                "I couldn't finalize the verified document safely. "
                "The same approved revision can be retried without "
                "duplicating storage or actions."
            ),
        }


def _create_domain_record(
    session,
    action: Dict[str, Any],
    user_id: str,
    document_id: Optional[str],
) -> Tuple[str, str, str]:
    """Create one approved domain record without committing.
    Returns ``(linked_domain, record_id, summary)``.  The caller writes the
    DocumentLink and ExecutionLedger in the same transaction before commit.
    """
    operation = str(action.get("operation") or "").strip()
    args = dict(action.get("arguments") or {})
    if operation == "log_expense":
        amount = int(args["amount_minor"])
        if amount <= 0:
            raise DocumentExecutionError(
                "Expense amount must be greater than zero."
            )
        occurred_at = _parse_datetime(
            args.get("occurred_at"),
            "occurred_at",
        )
        if occurred_at is None:
            raise DocumentExecutionError(
                "Document-derived expense is missing occurred_at."
            )
        row = Expense(
            amount_minor=amount,
            currency=str(args.get("currency") or "USD").upper(),
            category=str(args["category"]).strip(),
            description=(str(args.get("description") or "").strip() or None),
            occurred_at=occurred_at,
            recorded_by=user_id,
            document_id=document_id,
        )
        session.add(row)
        session.flush()
        return "finance", str(row.expense_id), (
            "Recorded expense {0:.2f} {1} under {2}.".format(
                amount / 100.0,
                row.currency,
                row.category,
            )
        )
    if operation == "create_recurring_bill":
        expected = args.get("expected_amount_minor")
        if expected is not None:
            expected = int(expected)
            if expected < 0:
                raise DocumentExecutionError(
                    "Recurring bill amount cannot be negative."
                )
        due_at = _parse_datetime(args.get("due_at"), "due_at")
        if due_at is None:
            raise DocumentExecutionError(
                "Recurring bill is missing due_at."
            )
        row = RecurringBill(
            payee=str(args["payee"]).strip(),
            due_at=due_at,
            expected_amount_minor=expected,
            currency=str(args.get("currency") or "USD").upper(),
            category=(str(args.get("category") or "").strip() or None),
            recurrence=str(args.get("recurrence") or "MONTHLY").strip(),
        )
        session.add(row)
        session.flush()
        return "finance", str(row.bill_id), (
            "Created recurring bill for {0}.".format(row.payee)
        )
    if operation == "add_grocery_item":
        row = GroceryItem(
            name=str(args["name"]).strip(),
            quantity=float(args.get("quantity", 1) or 1),
            unit=(str(args.get("unit") or "").strip() or None),
            purchased=False,
            added_by=user_id,
        )
        session.add(row)
        session.flush()
        return "food", str(row.grocery_item_id), (
            "Added {0} to the grocery list.".format(row.name)
        )
    if operation == "add_inventory_item":
        row = InventoryItem(
            name=str(args["name"]).strip(),
            quantity=float(args.get("quantity", 1) or 1),
            unit=(str(args.get("unit") or "").strip() or None),
            low_stock_threshold=(
                float(args["low_stock_threshold"])
                if args.get("low_stock_threshold") is not None
                else None
            ),
        )
        session.add(row)
        session.flush()
        return "food", str(row.item_id), (
            "Added {0} to inventory.".format(row.name)
        )
    if operation == "create_task":
        assigned_to = _resolve_active_user(
            session,
            args.get("assigned_to"),
        )
        row = Task(
            title=str(args["title"]).strip(),
            description=(str(args.get("description") or "").strip() or None),
            assigned_to=assigned_to,
            created_by=user_id,
            due_at=_parse_datetime(args.get("due_at"), "due_at"),
            priority=_parse_priority(args.get("priority")),
            status=TaskStatus.OPEN,
        )
        session.add(row)
        session.flush()

        # ---  NOTIFICATION ------------------------------------------
        if assigned_to and assigned_to != user_id:
            from app.models.notifications import Notification
            session.add(
                Notification(
                    user_id=assigned_to,
                    title="New Task from Document",
                    message=f"A task was created from an uploaded document: '{row.title}'",
                )
            )
        #----------------------------------------------------------------

        return "tasks", str(row.task_id), (
            "Created task '{0}'.".format(row.title)
        )
    if operation == "create_calendar_event":
        starts_at = _parse_datetime(args["starts_at"], "starts_at")
        ends_at = _parse_datetime(args["ends_at"], "ends_at")
        if starts_at is None or ends_at is None or ends_at <= starts_at:
            raise DocumentExecutionError(
                "Calendar event has an invalid time range."
            )
        row = CalendarEvent(
            title=str(args["title"]).strip(),
            starts_at=starts_at,
            ends_at=ends_at,
            owner_id=_resolve_active_user(session, args.get("owner_id")),
            task_id=(str(args.get("task_id") or "").strip() or None),
        )
        session.add(row)
        session.flush()
        return "tasks", str(row.event_id), (
            "Created calendar event '{0}'.".format(row.title)
        )
    if operation == "add_appliance":
        row = Appliance(
            name=str(args["name"]).strip(),
            brand=(str(args.get("brand") or "").strip() or None),
            model=(str(args.get("model") or "").strip() or None),
            purchased_at=_parse_date(args.get("purchased_at"), "purchased_at"),
            warranty_ends_at=_parse_date(
                args.get("warranty_ends_at"),
                "warranty_ends_at",
            ),
        )
        session.add(row)
        session.flush()
        return "maintenance", str(row.appliance_id), (
            "Added appliance '{0}'.".format(row.name)
        )
    if operation == "report_issue":
        row = MaintenanceIssue(
            description=str(args["description"]).strip(),
            appliance_id=_resolve_appliance(
                session,
                args.get("appliance_id"),
            ),
            priority=_parse_priority(args.get("priority")),
            status=IssueStatus.OPEN,
            reported_by=user_id,
        )
        session.add(row)
        session.flush()
        return "maintenance", str(row.issue_id), (
            "Reported maintenance issue."
        )
    if operation == "log_repair":
        serviced_at = _parse_date(
            args.get("serviced_at"),
            "serviced_at",
        )
        if serviced_at is None:
            raise DocumentExecutionError(
                "Document-derived repair is missing serviced_at."
            )
        row = Repair(
            appliance_id=_resolve_appliance(
                session,
                args.get("appliance_id"),
            ),
            serviced_at=serviced_at,
            provider=(str(args.get("provider") or "").strip() or None),
            cost_minor=(
                int(args["cost_minor"])
                if args.get("cost_minor") is not None
                else None
            ),
            currency=str(args.get("currency") or "USD").upper(),
            notes=(str(args.get("notes") or "").strip() or None),
            logged_by=user_id,
        )
        if row.cost_minor is not None and row.cost_minor < 0:
            raise DocumentExecutionError("Repair cost cannot be negative.")
        session.add(row)
        session.flush()
        return "maintenance", str(row.repair_id), "Logged repair record."
    raise DocumentExecutionError(
        "Unsupported approved document operation '{0}'.".format(operation)
    )


def _action_execution_is_stale(
    ledger: ExecutionLedger,
    now: Optional[datetime] = None,
) -> bool:
    """Return whether an interrupted action claim may be recovered."""

    if ledger.status != "RUNNING":
        return False

    if ledger.updated_at is None:
        return True

    now = now or utcnow()
    comparable_now = _comparable_datetime(
        ledger.updated_at,
        now,
    )
    return (
        ledger.updated_at
        <= comparable_now - _ACTION_STALE_AFTER
    )




def _replayed_action_result(
    ledger: ExecutionLedger,
    expected_key: str,
) -> Dict[str, Any]:
    """Load a completed result only when it matches approved arguments."""

    if ledger.idempotency_key != expected_key:
        raise DocumentExecutionError(
            "Stored execution arguments do not match "
            "the approved revision."
        )

    result = _read_ledger_result(ledger)
    result["replayed"] = True
    return result




def _claim_action_execution(
    proposal: WorkflowProposal,
    action_index: int,
    operation: str,
    arguments: Dict[str, Any],
    key: str,
) -> Tuple[str, Optional[Dict[str, Any]], Optional[datetime]]:
    """Atomically claim one approved action before any domain mutation."""

    session = SessionLocal()
    proposal_id = str(proposal.proposal_id)
    revision = int(proposal.revision)
    arguments_json = _canonical_json(arguments)

    try:
        ledger = session.query(ExecutionLedger).filter(
            ExecutionLedger.proposal_id == proposal_id,
            ExecutionLedger.revision == revision,
            ExecutionLedger.action_index == action_index,
        ).first()

        if ledger is None:
            claim_time = utcnow()
            ledger = ExecutionLedger(
                proposal_id=proposal_id,
                revision=revision,
                action_index=action_index,
                idempotency_key=key,
                operation=operation,
                arguments_json=arguments_json,
                status="RUNNING",
                started_at=claim_time,
                updated_at=claim_time,
            )
            session.add(ledger)
            session.commit()
            return str(ledger.execution_id), None, claim_time

        if ledger.idempotency_key != key:
            raise DocumentExecutionError(
                "Stored execution arguments do not match "
                "the approved revision."
            )

        if ledger.status == "COMPLETED":
            return (
                str(ledger.execution_id),
                _replayed_action_result(ledger, key),
                None,
            )

        if (
            ledger.status == "RUNNING"
            and not _action_execution_is_stale(ledger)
        ):
            raise DocumentExecutionError(
                "This approved action is already being executed."
            )

        if ledger.status not in {
            "PENDING",
            "RUNNING",
            "FAILED",
        }:
            raise DocumentExecutionError(
                "This approved action is not available for execution."
            )

        observed_status = str(ledger.status)
        observed_updated_at = ledger.updated_at
        claim_time = utcnow()

        claim_query = session.query(ExecutionLedger).filter(
            ExecutionLedger.execution_id == ledger.execution_id,
            ExecutionLedger.idempotency_key == key,
            ExecutionLedger.status == observed_status,
        )

        if observed_updated_at is None:
            claim_query = claim_query.filter(
                ExecutionLedger.updated_at.is_(None)
            )
        else:
            claim_query = claim_query.filter(
                ExecutionLedger.updated_at == observed_updated_at
            )

        changed = claim_query.update(
            {
                ExecutionLedger.status: "RUNNING",
                ExecutionLedger.arguments_json: arguments_json,
                ExecutionLedger.result_json: None,
                ExecutionLedger.error_message: None,
                ExecutionLedger.started_at: claim_time,
                ExecutionLedger.completed_at: None,
                ExecutionLedger.updated_at: claim_time,
            },
            synchronize_session=False,
        )

        if changed != 1:
            session.rollback()
            raise DocumentExecutionError(
                "This approved action was claimed by another request."
            )

        execution_id = str(ledger.execution_id)
        session.commit()
        return execution_id, None, claim_time

    except IntegrityError as exc:
        session.rollback()

        concurrent = session.query(ExecutionLedger).filter(
            ExecutionLedger.proposal_id == proposal_id,
            ExecutionLedger.revision == revision,
            ExecutionLedger.action_index == action_index,
        ).first()

        if concurrent is not None:
            if concurrent.idempotency_key != key:
                raise DocumentExecutionError(
                    "Stored execution arguments do not match "
                    "the approved revision."
                ) from exc

            if concurrent.status == "COMPLETED":
                return (
                    str(concurrent.execution_id),
                    _replayed_action_result(concurrent, key),
                    None,
                )

        raise DocumentExecutionError(
            "This approved action was claimed by another request."
        ) from exc

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()




def _record_action_failure(
    execution_id: str,
    key: str,
    claim_time: datetime,
    error: Exception,
) -> Optional[Dict[str, Any]]:
    """Record failure only while this request still owns the claim."""

    session = SessionLocal()

    try:
        changed = session.query(ExecutionLedger).filter(
            ExecutionLedger.execution_id == execution_id,
            ExecutionLedger.idempotency_key == key,
            ExecutionLedger.status == "RUNNING",
            ExecutionLedger.updated_at == claim_time,
        ).update(
            {
                ExecutionLedger.status: "FAILED",
                ExecutionLedger.error_message: str(error),
                ExecutionLedger.updated_at: utcnow(),
            },
            synchronize_session=False,
        )

        if changed == 1:
            session.commit()
            return None

        session.rollback()
        ledger = session.get(ExecutionLedger, execution_id)

        if (
            ledger is not None
            and ledger.status == "COMPLETED"
        ):
            return _replayed_action_result(ledger, key)

        return None

    except Exception:
        session.rollback()
        return None

    finally:
        session.close()




def _execute_one_action(
    proposal: WorkflowProposal,
    action_index: int,
    action: Dict[str, Any],
    user_id: str,
    document_id: Optional[str],
) -> Dict[str, Any]:
    """Execute one action only after obtaining its durable ledger claim."""

    operation = str(action.get("operation") or "").strip()
    arguments = dict(action.get("arguments") or {})
    key = _ledger_key(
        str(proposal.proposal_id),
        int(proposal.revision),
        action_index,
        operation,
        arguments,
    )

    execution_id, replayed, claim_time = _claim_action_execution(
        proposal,
        action_index,
        operation,
        arguments,
        key,
    )

    if replayed is not None:
        return replayed

    if claim_time is None:
        raise DocumentExecutionError(
            "The approved action claim is invalid."
        )

    session = SessionLocal()

    try:
        linked_domain, record_id, summary = _create_domain_record(
            session,
            action,
            user_id,
            document_id,
        )

        if document_id is not None:
            existing_link = session.query(DocumentLink).filter(
                DocumentLink.linked_domain == linked_domain,
                DocumentLink.linked_record_id == record_id,
            ).first()

            if existing_link is None:
                session.add(
                    DocumentLink(
                        document_id=document_id,
                        linked_domain=linked_domain,
                        linked_record_id=record_id,
                    )
                )
            elif str(existing_link.document_id) != str(document_id):
                raise DocumentExecutionError(
                    "The created record is already linked to "
                    "a different document."
                )

        result = {
            "action_index": action_index,
            "operation": operation,
            "status": "COMPLETED",
            "linked_domain": linked_domain,
            "record_id": record_id,
            "document_id": document_id,
            "summary": summary,
            "replayed": False,
        }
        completed_at = utcnow()

        changed = session.query(ExecutionLedger).filter(
            ExecutionLedger.execution_id == execution_id,
            ExecutionLedger.idempotency_key == key,
            ExecutionLedger.status == "RUNNING",
            ExecutionLedger.updated_at == claim_time,
        ).update(
            {
                ExecutionLedger.status: "COMPLETED",
                ExecutionLedger.result_json: _canonical_json(result),
                ExecutionLedger.error_message: None,
                ExecutionLedger.completed_at: completed_at,
                ExecutionLedger.updated_at: completed_at,
            },
            synchronize_session=False,
        )

        if changed != 1:
            raise DocumentExecutionError(
                "The approved action claim is no longer owned "
                "by this request."
            )

        # Domain row, DocumentLink, and completion transition commit together.
        session.commit()
        return result

    except Exception as exc:
        session.rollback()
        replayed_after_failure = _record_action_failure(
            execution_id,
            key,
            claim_time,
            exc,
        )

        if replayed_after_failure is not None:
            return replayed_after_failure

        if isinstance(exc, DocumentExecutionError):
            raise

        raise DocumentExecutionError(
            "Approved action '{0}' failed.".format(operation)
        ) from exc

    finally:
        session.close()


def execute_approved_document(
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """Execute one exact approved document proposal revision."""
    (
        user_id,
        conversation_id,
        session_id,
    ) = _execution_scope(state)
    session = SessionLocal()
    try:
        row = _query_execution_row(
            session,
            state,
        )
        if row is None:
            raise DocumentExecutionError(
                "There is no approved document "
                "proposal waiting to execute."
            )
        payload = _load_payload(
            row
        )
        # These checks are intentionally unconditional.
        # Ownerless legacy workflow rows cannot execute.
        if str(row.user_id or "") != user_id:
            raise DocumentExecutionError(
                "The approved document proposal "
                "is unavailable."
            )
        if (
            str(row.conversation_id or "")
            != conversation_id
        ):
            raise DocumentExecutionError(
                "The approved document proposal "
                "is unavailable."
            )
        if (
            str(row.session_id or "")
            != session_id
        ):
            raise DocumentExecutionError(
                "The approved document proposal "
                "is unavailable."
            )
        if (
            str(row.approved_by or "")
            != user_id
        ):
            raise DocumentExecutionError(
                "The approved document proposal "
                "is unavailable."
            )
        row_pending_id = str(
            row.pending_document_id or ""
        ).strip()
        payload_pending_id = str(
            payload.get(
                "pending_document_id"
            )
            or ""
        ).strip()
        if (
            not row_pending_id
            or not payload_pending_id
            or row_pending_id
            != payload_pending_id
        ):
            raise DocumentExecutionError(
                "The approved proposal has an "
                "invalid staged document reference."
            )
        pending = (
            session.query(
                PendingDocumentUpload
            )
            .filter(
                PendingDocumentUpload.pending_id
                == row_pending_id,
                PendingDocumentUpload.uploaded_by
                == user_id,
            )
            .first()
        )
        if pending is None:
            raise DocumentExecutionError(
                "The staged document is unavailable."
            )

        workflow_kind = str(row.kind or "")
        phase = str(payload.get("phase") or "")
        is_interpretation_finalization = (
            workflow_kind == DOCUMENT_REVIEW_KIND
            and phase == "interpretation_verified"
        )
        is_separated_action = (
            workflow_kind == DOCUMENT_ACTION_KIND
            and phase == "action_review"
        )

        if workflow_kind == DOCUMENT_ACTION_KIND and not is_separated_action:
            raise DocumentExecutionError(
                "The derived-action proposal has an invalid phase."
            )

        if is_separated_action:
            source_id = str(
                payload.get("source_proposal_id") or ""
            ).strip()
            source_revision = payload.get("source_revision")
            source_hash = str(
                payload.get("source_args_hash") or ""
            ).strip()
            if not source_id or not source_hash:
                raise DocumentExecutionError(
                    "The derived-action proposal has invalid provenance."
                )
            source = session.query(WorkflowProposal).filter(
                WorkflowProposal.proposal_id == source_id,
                WorkflowProposal.user_id == user_id,
                WorkflowProposal.conversation_id == conversation_id,
                WorkflowProposal.session_id == session_id,
                WorkflowProposal.kind == DOCUMENT_REVIEW_KIND,
                WorkflowProposal.status == "COMPLETED",
                WorkflowProposal.revision == source_revision,
                WorkflowProposal.args_hash == source_hash,
                WorkflowProposal.pending_document_id == row_pending_id,
                WorkflowProposal.approved_by == user_id,
            ).first()
            if source is None:
                raise DocumentExecutionError(
                    "The verified source for these actions is unavailable."
                )
            source_payload = _load_payload(source)
            source_decision = source_payload.get("document_decision") or {}
            if (
                not isinstance(source_decision, dict)
                or source_decision.get("interpretation_verified") is not True
                or source_decision.get("store_document")
                is not payload.get("store_document")
            ):
                raise DocumentExecutionError(
                    "The derived-action storage decision does not match "
                    "its verified source."
                )

            action_store_document = payload.get("store_document")
            action_document_id = str(
                payload.get("document_id") or ""
            ).strip()
            if not isinstance(action_store_document, bool):
                raise DocumentExecutionError(
                    "The derived-action storage decision is invalid."
                )
            if action_store_document and not action_document_id:
                raise DocumentExecutionError(
                    "The stored source document is unavailable."
                )
            if not action_store_document and action_document_id:
                raise DocumentExecutionError(
                    "An unstored source cannot reference a permanent document."
                )
            if action_document_id:
                document = session.query(Document).filter(
                    Document.document_id == action_document_id,
                    Document.uploaded_by == user_id,
                    Document.status == "approved",
                ).first()
                if document is None:
                    raise DocumentExecutionError(
                        "The stored source document is unavailable."
                    )

        proposal_payload = (
            payload.get(
                "document_proposal"
            )
            or {}
        )
        actions = [
            dict(action)
            for action in (
                proposal_payload.get(
                    "actions"
                )
                or []
            )
            if isinstance(action, dict)
        ]
        ready_actions = [
            (
                index,
                action,
            )
            for index, action in enumerate(
                actions
            )
            if not action.get("blocked")
        ]
        if not ready_actions and not is_interpretation_finalization:
            raise DocumentExecutionError(
                "The approved proposal has no "
                "executable actions."
            )
        # Claim this exact approved revision before running
        # preflight, archive, or domain mutations.
        _claim_document_execution(
            session,
            row,
            state,
        )
        role = str(state.get("role") or "")
        failures: List[
            Dict[str, Any]
        ] = []
        completed_action_indexes: List[int] = []
        for (
            action_index,
            action,
        ) in (
            []
            if is_interpretation_finalization
            else ready_actions
        ):
            try:
                if _completed_action_matches_ledger(
                    session,
                    row,
                    action_index,
                    action,
                ):
                    completed_action_indexes.append(action_index)
                    reasons = []
                else:
                    reasons = _preflight_action(
                        session,
                        action,
                        role,
                    )
            except DocumentExecutionError as exc:
                reasons = [
                    str(exc)
                ]
            if reasons:
                failures.append(
                    {
                        "action_index": (
                            action_index
                        ),
                        "operation": (
                            action.get(
                                "operation"
                            )
                        ),
                        "reasons": reasons,
                    }
                )
        if failures:
            revised = _return_to_review(
                row,
                payload,
                failures,
                completed_action_indexes,
            )
            pending.status = (
                "awaiting_action_review"
                if is_separated_action
                else "needs_review"
            )
            session.commit()
            return {
                "status": "REVIEW_REQUIRED",
                "confirmation_kind": (
                    DOCUMENT_ACTION_KIND
                    if is_separated_action
                    else DOCUMENT_REVIEW_KIND
                ),
                "proposal_id": (
                    revised["proposal_id"]
                ),
                "revision": (
                    revised["revision"]
                ),
                "pending_document_id": (
                    row_pending_id
                ),
                "execution_results": [],
                "response": (
                    "I rechecked the approved actions "
                    "and found a new permission, "
                    "duplicate, entity, or schedule "
                    "conflict. Nothing was executed. "
                    "I created a new blocked review "
                    "revision; edit the affected action "
                    "before approving again."
                ),
            }
        proposal_snapshot = WorkflowProposal(
            proposal_id=row.proposal_id,
            session_id=session_id,
            conversation_id=conversation_id,
            user_id=user_id,
            kind=row.kind,
            revision=row.revision,
            payload_json=row.payload_json,
            args_hash=row.args_hash,
            pending_document_id=(
                row_pending_id
            ),
            status=row.status,
            approved_at=row.approved_at,
            approved_by=user_id,
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    # Reload pending in a fresh detached-safe session for archive metadata.
    meta_session = SessionLocal()
    try:
        pending = (
            meta_session.query(
                PendingDocumentUpload
            )
            .filter(
                PendingDocumentUpload.pending_id
                == str(
                    proposal_snapshot.pending_document_id
                ),
                PendingDocumentUpload.uploaded_by
                == user_id,
            )
            .first()
        )
        if pending is None:
            raise DocumentExecutionError(
                "The staged document no longer exists."
            )
        # Copy the values needed after closing the session.
        pending_snapshot = PendingDocumentUpload(
            pending_id=pending.pending_id,
            upload_id=pending.upload_id,
            uploaded_by=pending.uploaded_by,
            original_filename=pending.original_filename,
            safe_filename=pending.safe_filename,
            temp_path=pending.temp_path,
            mime_type=pending.mime_type,
            extension=pending.extension,
            file_size=pending.file_size,
            sha256=pending.sha256,
            normalized_text_hash=pending.normalized_text_hash,
            visual_hashes_json=pending.visual_hashes_json,
            extracted_text=pending.extracted_text,
            extraction_method=pending.extraction_method,
            page_count=pending.page_count,
            domain=pending.domain,
            classified_document_type=pending.classified_document_type,
            classification_confidence=pending.classification_confidence,
            classification_reason=pending.classification_reason,
            prompt_injection_detected=pending.prompt_injection_detected,
            status=pending.status,
            review_reasons_json=pending.review_reasons_json,
        )
    finally:
        meta_session.close()
    payload = _load_payload(proposal_snapshot)

    if (
        proposal_snapshot.kind == DOCUMENT_REVIEW_KIND
        and payload.get("phase") == "interpretation_verified"
    ):
        return _finalize_verified_interpretation(
            proposal_snapshot,
            pending_snapshot,
            payload,
            state,
        )

    if proposal_snapshot.kind == DOCUMENT_ACTION_KIND:
        store_document = payload.get("store_document")
        if not isinstance(store_document, bool):
            raise DocumentExecutionError(
                "The derived-action storage decision is invalid."
            )
        document_id_value = str(payload.get("document_id") or "").strip()
        document_id = document_id_value or None
        if store_document and document_id is None:
            raise DocumentExecutionError(
                "The stored source document is unavailable."
            )
        if not store_document and document_id is not None:
            raise DocumentExecutionError(
                "An unstored source cannot reference a permanent document."
            )
        if document_id is not None:
            validation_session = SessionLocal()
            try:
                document = validation_session.query(Document).filter(
                    Document.document_id == document_id,
                    Document.uploaded_by == user_id,
                    Document.status == "approved",
                ).first()
                if document is None:
                    raise DocumentExecutionError(
                        "The stored source document is unavailable."
                    )
            finally:
                validation_session.close()
        archive_result = {
            "stored": store_document,
            "document_id": document_id,
            "reused_from_interpretation": True,
        }
    else:
        # Backward-compatible path for an older single-gate proposal that was
        # approved before the separated workflow was deployed.
        document_id, archive_result = _archive_original(
            proposal_snapshot,
            pending_snapshot,
            payload,
        )
    execution_results: List[Dict[str, Any]] = []
    try:
        proposal_payload = payload.get("document_proposal") or {}
        actions = [
            dict(action or {})
            for action in (proposal_payload.get("actions") or [])
            if isinstance(action, dict)
        ]
        for action_index, action in enumerate(actions):
            if action.get("blocked"):
                continue
            result = _execute_one_action(
                proposal_snapshot,
                action_index,
                action,
                str(state.get("user_id") or ""),
                document_id,
            )
            execution_results.append(result)
        final_session = SessionLocal()
        try:
            final_row = final_session.get(
                WorkflowProposal,
                proposal_snapshot.proposal_id,
            )
            if final_row is None:
                raise DocumentExecutionError(
                    "The workflow proposal disappeared during execution."
                )
            final_row.status = "COMPLETED"
            final_row.updated_at = utcnow()
            final_row.last_error = None
            final_pending = final_session.get(
                PendingDocumentUpload,
                str(proposal_snapshot.pending_document_id),
            )
            if final_pending is not None:
                final_pending.status = "completed"
            final_session.commit()
        finally:
            final_session.close()
        cleanup_terminal_pending_upload(
            str(proposal_snapshot.pending_document_id)
        )
        summaries = [
            str(result.get("summary") or "").strip()
            for result in execution_results
            if str(result.get("summary") or "").strip()
        ]
        response_lines = ["Approved document actions completed."]
        if document_id is not None:
            response_lines.append("Original document stored securely.")
        elif proposal_snapshot.kind == DOCUMENT_ACTION_KIND:
            response_lines.append(
                "Original document was not stored, as requested."
            )
        response_lines.extend("- " + summary for summary in summaries)
        return {
            "status": "COMPLETED",
            "proposal_id": str(proposal_snapshot.proposal_id),
            "revision": int(proposal_snapshot.revision),
            "pending_document_id": str(proposal_snapshot.pending_document_id),
            "document_id": document_id,
            "archive": archive_result,
            "execution_results": execution_results,
            "response": "\n".join(response_lines),
        }
    except Exception as exc:
        failure_session = SessionLocal()
        try:
            final_row = failure_session.get(
                WorkflowProposal,
                proposal_snapshot.proposal_id,
            )
            if final_row is not None:
                final_row.status = "FAILED"
                final_row.updated_at = utcnow()
                final_row.last_error = str(exc)
            failed_pending = failure_session.get(
                PendingDocumentUpload,
                str(proposal_snapshot.pending_document_id),
            )
            if failed_pending is not None:
                failed_pending.status = "execution_failed"
            failure_session.commit()
        finally:
            failure_session.close()
        if isinstance(exc, DocumentExecutionError):
            message = str(exc)
        else:
            message = "An approved document action failed during execution."
        return {
            "status": "FAILED",
            "proposal_id": str(proposal_snapshot.proposal_id),
            "revision": int(proposal_snapshot.revision),
            "pending_document_id": str(proposal_snapshot.pending_document_id),
            "document_id": document_id,
            "archive": archive_result,
            "execution_results": execution_results,
            "response": (
                message
                + (
                    " The original document is safely stored."
                    if document_id is not None
                    else " The original document was not stored."
                )
                + " Completed actions were not rolled back; the execution "
                "ledger prevents them from being duplicated on a later retry."
            ),
        }


def document_execute_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph node for approved document execution."""
    try:
        result = execute_approved_document(state)
    except DocumentExecutionError as exc:
        return {
            "document_execution_status": "FAILED",
            "document_execution_results": [],
            "awaiting_confirmation": False,
            "finished": True,
            "response": str(exc),
        }
    except Exception:
        return {
            "document_execution_status": "FAILED",
            "document_execution_results": [],
            "awaiting_confirmation": False,
            "finished": True,
            "response": (
                "I couldn't execute the approved document proposal safely. "
                "No new action should be retried manually until the workflow "
                "status is checked."
            ),
        }
    status = str(result.get("status") or "FAILED")
    action_review_required = status == "ACTION_REVIEW_REQUIRED"
    ordinary_review_required = status == "REVIEW_REQUIRED"
    return {
        "workflow_proposal_id": (
            result.get("action_proposal_id")
            if action_review_required
            else result.get("proposal_id")
        ),
        "pending_document_id": result.get("pending_document_id"),
        "archived_document_id": result.get("document_id"),
        "document_execution_status": status,
        "document_execution_results": list(
            result.get("execution_results") or []
        ),
        "confirmation_kind": (
            result.get("confirmation_kind")
            if action_review_required or ordinary_review_required
            else None
        ),
        "awaiting_confirmation": (
            action_review_required or ordinary_review_required
        ),
        "finished": True,
        "response": str(result.get("response") or ""),
    }
