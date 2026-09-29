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
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func

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
from app.storage.cloudinary_storage import delete_file, upload_file
from app.storage.temp_storage import delete_temp_file


class DocumentExecutionError(RuntimeError):
    """Raised when approved document execution cannot continue safely."""


_ARCHIVE_ACTION_INDEX = -1
_ARCHIVE_OPERATION = "__archive_document__"


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


def _state_key(state: Dict[str, Any]) -> str:
    return str(
        state.get("session_id")
        or state.get("conversation_id")
        or ""
    ).strip()


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


def _query_execution_row(
    session,
    state: Dict[str, Any],
) -> Optional[WorkflowProposal]:
    key = _state_key(state)
    proposal_id = str(state.get("workflow_proposal_id") or "").strip()

    if not key:
        return None

    query = session.query(WorkflowProposal).filter(
        WorkflowProposal.session_id == key,
        WorkflowProposal.kind == "document",
        WorkflowProposal.status.in_(["APPROVED", "EXECUTING"]),
    )

    user_id = state.get("user_id")
    if user_id:
        query = query.filter(
            WorkflowProposal.user_id == str(user_id)
        )

    if proposal_id:
        query = query.filter(
            WorkflowProposal.proposal_id == proposal_id
        )

    return query.order_by(
        desc(WorkflowProposal.updated_at),
        desc(WorkflowProposal.created_at),
    ).first()


def find_resumable_document_execution(
    state: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Return an already-approved execution that should resume after restart."""

    session = SessionLocal()
    try:
        row = _query_execution_row(session, state)
        if row is None:
            return None

        return {
            "proposal_id": str(row.proposal_id),
            "revision": int(row.revision or 1),
            "pending_document_id": row.pending_document_id,
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


def _return_to_review(
    row: WorkflowProposal,
    payload: Dict[str, Any],
    failures: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Invalidate stale approval and create a new blocked review revision."""

    proposal = dict(payload.get("document_proposal") or {})
    actions = [
        dict(action or {})
        for action in (proposal.get("actions") or [])
    ]
    warnings = list(proposal.get("warnings") or [])

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

    row.revision = int(row.revision or 0) + 1
    row.payload_json = _canonical_json(payload)
    row.args_hash = _hash_json(payload)
    row.status = "AWAITING_REVIEW"
    row.approved_by = None
    row.approved_at = None
    row.updated_at = utcnow()
    row.last_error = "Fresh execution checks require another review."

    return {
        "proposal_id": str(row.proposal_id),
        "revision": int(row.revision),
        "payload": payload,
    }


def _archive_original(
    proposal: WorkflowProposal,
    pending: PendingDocumentUpload,
    payload: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    """Archive the staged original once, using a deterministic object key."""

    session = SessionLocal()
    cloud_result: Optional[Dict[str, Any]] = None

    try:
        existing = session.query(ExecutionLedger).filter(
            ExecutionLedger.proposal_id == proposal.proposal_id,
            ExecutionLedger.revision == proposal.revision,
            ExecutionLedger.action_index == _ARCHIVE_ACTION_INDEX,
        ).first()

        if existing is not None and existing.status == "COMPLETED":
            result = _read_ledger_result(existing)
            document_id = str(result.get("document_id") or "")
            if document_id:
                document = session.get(Document, document_id)
                if document is not None:
                    return document_id, result

        temp_path = str(pending.temp_path or "")
        if not temp_path or not os.path.exists(temp_path):
            raise DocumentExecutionError(
                "The staged original file is no longer available."
            )

        deterministic_public_id = "document_{0}".format(pending.pending_id)
        cloud_result = upload_file(
            temp_path,
            public_id=deterministic_public_id,
            overwrite=True,
        )

        public_id = str(cloud_result.get("public_id") or "").strip()
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
            file_size=(cloud_result.get("bytes") or pending.file_size),
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
            uploaded_by=pending.uploaded_by,
        )
        session.add(document)
        session.flush()

        result = {
            "document_id": str(document.document_id),
            "public_id": public_id,
            "resource_type": cloud_result.get("resource_type"),
            "format": cloud_result.get("format"),
            "asset_id": cloud_result.get("asset_id"),
        }

        ledger = existing
        if ledger is None:
            ledger = ExecutionLedger(
                proposal_id=str(proposal.proposal_id),
                revision=int(proposal.revision),
                action_index=_ARCHIVE_ACTION_INDEX,
                idempotency_key=_ledger_key(
                    str(proposal.proposal_id),
                    int(proposal.revision),
                    _ARCHIVE_ACTION_INDEX,
                    _ARCHIVE_OPERATION,
                    {"pending_document_id": str(pending.pending_id)},
                ),
                operation=_ARCHIVE_OPERATION,
                arguments_json=_canonical_json(
                    {"pending_document_id": str(pending.pending_id)}
                ),
            )
            session.add(ledger)

        ledger.status = "COMPLETED"
        ledger.result_json = _canonical_json(result)
        ledger.error_message = None
        ledger.started_at = ledger.started_at or utcnow()
        ledger.completed_at = utcnow()
        ledger.updated_at = utcnow()

        db_pending = session.get(PendingDocumentUpload, pending.pending_id)
        if db_pending is not None:
            db_pending.status = "archived_pending_actions"

        session.commit()

        try:
            delete_temp_file(temp_path)
        except Exception:
            # Permanent storage + DB metadata are already authoritative.
            pass

        return str(document.document_id), result

    except Exception as exc:
        session.rollback()

        # A concurrent/resumed execution may have committed the deterministic
        # archive while this transaction was losing a uniqueness race. Recheck
        # before deleting the shared Cloudinary key.
        verify_session = SessionLocal()
        try:
            committed = verify_session.query(ExecutionLedger).filter(
                ExecutionLedger.proposal_id == proposal.proposal_id,
                ExecutionLedger.revision == proposal.revision,
                ExecutionLedger.action_index == _ARCHIVE_ACTION_INDEX,
                ExecutionLedger.status == "COMPLETED",
            ).first()
            if committed is not None:
                result = _read_ledger_result(committed)
                document_id = str(result.get("document_id") or "")
                if document_id and verify_session.get(Document, document_id) is not None:
                    return document_id, result
        finally:
            verify_session.close()

        if cloud_result and cloud_result.get("public_id"):
            try:
                delete_file(
                    str(cloud_result.get("public_id")),
                    resource_type=str(
                        cloud_result.get("resource_type") or "image"
                    ),
                )
            except Exception:
                pass

        if isinstance(exc, DocumentExecutionError):
            raise
        raise DocumentExecutionError(
            "Unable to archive the approved original document."
        ) from exc
    finally:
        session.close()


def _create_domain_record(
    session,
    action: Dict[str, Any],
    user_id: str,
    document_id: str,
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


def _execute_one_action(
    proposal: WorkflowProposal,
    action_index: int,
    action: Dict[str, Any],
    user_id: str,
    document_id: str,
) -> Dict[str, Any]:
    session = SessionLocal()

    operation = str(action.get("operation") or "").strip()
    arguments = dict(action.get("arguments") or {})
    key = _ledger_key(
        str(proposal.proposal_id),
        int(proposal.revision),
        action_index,
        operation,
        arguments,
    )

    try:
        ledger = session.query(ExecutionLedger).filter(
            ExecutionLedger.proposal_id == proposal.proposal_id,
            ExecutionLedger.revision == proposal.revision,
            ExecutionLedger.action_index == action_index,
        ).first()

        if ledger is not None and ledger.status == "COMPLETED":
            result = _read_ledger_result(ledger)
            result["replayed"] = True
            return result

        if ledger is None:
            ledger = ExecutionLedger(
                proposal_id=str(proposal.proposal_id),
                revision=int(proposal.revision),
                action_index=action_index,
                idempotency_key=key,
                operation=operation,
                arguments_json=_canonical_json(arguments),
            )
            session.add(ledger)
        else:
            if ledger.idempotency_key != key:
                raise DocumentExecutionError(
                    "Stored execution arguments do not match the approved revision."
                )
            ledger.arguments_json = _canonical_json(arguments)

        ledger.status = "RUNNING"
        ledger.started_at = ledger.started_at or utcnow()
        ledger.updated_at = utcnow()
        ledger.error_message = None

        linked_domain, record_id, summary = _create_domain_record(
            session,
            action,
            user_id,
            document_id,
        )

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
                "The created record is already linked to a different document."
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

        ledger.status = "COMPLETED"
        ledger.result_json = _canonical_json(result)
        ledger.error_message = None
        ledger.completed_at = utcnow()
        ledger.updated_at = utcnow()

        # Domain row + DocumentLink + ledger commit atomically.
        session.commit()
        return result

    except Exception as exc:
        session.rollback()

        # Persist failure separately after the failed domain transaction has
        # been rolled back.  No domain record exists unless a prior completed
        # ledger already proved it committed.
        failure_session = SessionLocal()
        try:
            ledger = failure_session.query(ExecutionLedger).filter(
                ExecutionLedger.proposal_id == proposal.proposal_id,
                ExecutionLedger.revision == proposal.revision,
                ExecutionLedger.action_index == action_index,
            ).first()

            if ledger is None:
                ledger = ExecutionLedger(
                    proposal_id=str(proposal.proposal_id),
                    revision=int(proposal.revision),
                    action_index=action_index,
                    idempotency_key=key,
                    operation=operation,
                    arguments_json=_canonical_json(arguments),
                )
                failure_session.add(ledger)

            ledger.status = "FAILED"
            ledger.error_message = str(exc)
            ledger.updated_at = utcnow()
            failure_session.commit()
        except Exception:
            failure_session.rollback()
        finally:
            failure_session.close()

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

    session = SessionLocal()

    try:
        row = _query_execution_row(session, state)
        if row is None:
            raise DocumentExecutionError(
                "There is no approved document proposal waiting to execute."
            )

        payload = _load_payload(row)

        user_id = str(state.get("user_id") or "").strip()
        if not user_id:
            raise DocumentExecutionError(
                "Document execution requires an authenticated user."
            )

        if row.user_id and str(row.user_id) != user_id:
            raise DocumentExecutionError(
                "This approved document proposal belongs to another user."
            )

        if row.approved_by and str(row.approved_by) != user_id:
            raise DocumentExecutionError(
                "This document proposal was approved by another user."
            )

        pending_id = row.pending_document_id or payload.get(
            "pending_document_id"
        )
        if not pending_id:
            raise DocumentExecutionError(
                "The approved proposal has no staged document reference."
            )

        pending = session.get(PendingDocumentUpload, str(pending_id))
        if pending is None:
            raise DocumentExecutionError(
                "The staged document no longer exists."
            )
        if pending.uploaded_by and str(pending.uploaded_by) != user_id:
            raise DocumentExecutionError(
                "The staged document belongs to another user."
            )

        proposal_payload = payload.get("document_proposal") or {}
        actions = [
            dict(action or {})
            for action in (proposal_payload.get("actions") or [])
            if isinstance(action, dict)
        ]

        ready_actions = [
            (index, action)
            for index, action in enumerate(actions)
            if not action.get("blocked")
        ]

        if not ready_actions:
            raise DocumentExecutionError(
                "The approved proposal has no executable actions."
            )

        role = str(state.get("role") or "")
        failures: List[Dict[str, Any]] = []

        for action_index, action in ready_actions:
            try:
                reasons = _preflight_action(session, action, role)
            except DocumentExecutionError as exc:
                reasons = [str(exc)]
            if reasons:
                failures.append(
                    {
                        "action_index": action_index,
                        "operation": action.get("operation"),
                        "reasons": reasons,
                    }
                )

        if failures:
            revised = _return_to_review(row, payload, failures)
            if pending is not None:
                pending.status = "needs_review"
            session.commit()

            return {
                "status": "REVIEW_REQUIRED",
                "proposal_id": revised["proposal_id"],
                "revision": revised["revision"],
                "pending_document_id": str(pending_id),
                "execution_results": [],
                "response": (
                    "I rechecked the approved actions and found a new "
                    "permission, duplicate, entity, or schedule conflict. "
                    "Nothing was executed. I created a new blocked review "
                    "revision; edit the affected action before approving again."
                ),
            }

        row.status = "EXECUTING"
        row.updated_at = utcnow()
        row.last_error = None
        session.commit()

        proposal_snapshot = WorkflowProposal(
            proposal_id=row.proposal_id,
            session_id=row.session_id,
            conversation_id=row.conversation_id,
            user_id=row.user_id,
            kind=row.kind,
            revision=row.revision,
            payload_json=row.payload_json,
            args_hash=row.args_hash,
            pending_document_id=row.pending_document_id,
            status=row.status,
            approved_at=row.approved_at,
            approved_by=row.approved_by,
        )

    except Exception:
        session.rollback()
        session.close()
        raise
    finally:
        # `proposal_snapshot` is detached intentionally; later helpers open
        # their own short-lived sessions.
        if session.is_active:
            session.close()

    # Reload pending in a fresh detached-safe session for archive metadata.
    meta_session = SessionLocal()
    try:
        pending = meta_session.get(
            PendingDocumentUpload,
            str(proposal_snapshot.pending_document_id),
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

        summaries = [
            str(result.get("summary") or "").strip()
            for result in execution_results
            if str(result.get("summary") or "").strip()
        ]

        response_lines = [
            "Approved document actions completed.",
            "Original document archived securely.",
        ]
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
                + " The original document is safely archived. Completed "
                "actions were not rolled back; the execution ledger prevents "
                "them from being duplicated on a later retry."
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

    return {
        "workflow_proposal_id": result.get("proposal_id"),
        "pending_document_id": result.get("pending_document_id"),
        "archived_document_id": result.get("document_id"),
        "document_execution_status": status,
        "document_execution_results": list(
            result.get("execution_results") or []
        ),
        "confirmation_kind": (
            "document"
            if status == "REVIEW_REQUIRED"
            else None
        ),
        "awaiting_confirmation": status == "REVIEW_REQUIRED",
        "finished": True,
        "response": str(result.get("response") or ""),
    }
