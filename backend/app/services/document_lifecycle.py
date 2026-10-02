"""Pending-document lifecycle cleanup for AI Home Manager.

This service owns lifecycle retirement for staged document uploads.  It keeps
request-path code small while ensuring abandoned, rejected, superseded, and
completed pending uploads do not retain temporary binaries or extracted OCR
text indefinitely.

Approved, executing, and failed uploads are protected during a bounded retry
window. After that window, the workflow is retired and transient binary/OCR
content is cleaned. Permanent documents and execution-ledger audit rows are
never removed by this service.

Compatibility target: Python 3.8+.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional, Set

from sqlalchemy import func, or_

from app.db.base import SessionLocal, utcnow
from app.models.documents import PendingDocumentUpload
from app.models.workflows import WorkflowProposal
from app.storage.temp_storage import delete_temp_file, get_temp_upload_dir


logger = logging.getLogger(__name__)

PENDING_DOCUMENT_TTL_HOURS = max(
    1,
    int(os.getenv("PENDING_DOCUMENT_TTL_HOURS", "24")),
)

DOCUMENT_EXECUTION_RETENTION_HOURS = max(
    1,
    int(os.getenv("DOCUMENT_EXECUTION_RETENTION_HOURS", "24")),
)

DOCUMENT_WORKFLOW_KINDS = (
    "document",
    "document_action",
)

ACTIVE_REVIEW_PENDING_STATUSES = (
    "staged",
    "needs_review",
    "awaiting_action_review",
)

RETIRED_PENDING_STATUSES = (
    "expired",
    "rejected_by_user",
    "superseded",
    "completed",
)

PROTECTED_PENDING_STATUSES = (
    "verified_pending_finalization",
    "approved_pending_execution",
    "archived_pending_actions",
    "execution_failed",
)

RECOVERABLE_DOCUMENT_WORKFLOW_STATUSES = (
    "APPROVED",
    "EXECUTING",
    "FAILED",
)

_WORKFLOW_TO_PENDING_TERMINAL_STATUS = {
    "REJECTED": "rejected_by_user",
    "CANCELLED": "superseded",
    "EXPIRED": "expired",
    "COMPLETED": "completed",
}


def _comparable_now(value: datetime, now: datetime) -> datetime:
    """Return ``now`` with timezone shape compatible with ``value``."""

    if value.tzinfo is None and now.tzinfo is not None:
        return now.replace(tzinfo=None)
    if value.tzinfo is not None and now.tzinfo is None:
        return now.replace(tzinfo=value.tzinfo)
    return now


def _is_expired(value: Optional[datetime], now: datetime) -> bool:
    if value is None:
        return False
    return value <= _comparable_now(value, now)


def _is_older_than(
    value: Optional[datetime],
    cutoff: datetime,
) -> bool:
    if value is None:
        return False
    return value <= _comparable_now(value, cutoff)


def _safe_pending_path(temp_path: str) -> Optional[Path]:
    """Resolve a staged path only when it is inside TEMP_UPLOAD_DIR."""

    raw = str(temp_path or "").strip()
    if not raw:
        return None

    try:
        root = get_temp_upload_dir().resolve()
        path = Path(raw).resolve()
    except Exception:
        logger.exception("Unable to resolve a pending document path.")
        return None

    if path == root or root not in path.parents:
        logger.error(
            "Refusing to clean a path outside TEMP_UPLOAD_DIR: %s",
            path,
        )
        return None

    return path


def _delete_pending_binary(temp_path: str) -> bool:
    """Delete a staged binary only from the configured pending directory."""

    raw = str(temp_path or "").strip()
    if not raw:
        return True

    path = _safe_pending_path(raw)
    if path is None:
        return False

    try:
        delete_temp_file(str(path))
        return not path.exists()
    except Exception:
        logger.exception("Unable to delete retired pending document binary.")
        return False


def mark_document_review_expired(
    session,
    row: WorkflowProposal,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Mark one review and its active pending upload expired in one DB txn.

    The caller owns the transaction.  External file deletion is intentionally
    deferred until after commit so a DB rollback can never leave an active row
    pointing at a binary that was already deleted.
    """

    now = now or utcnow()
    row.status = "EXPIRED"
    row.updated_at = now
    row.last_error = "Document review expired before a user decision."

    pending_id = str(row.pending_document_id or "").strip()
    if not pending_id:
        return None

    pending = session.get(PendingDocumentUpload, pending_id)
    if pending is None:
        return None

    if pending.status in ACTIVE_REVIEW_PENDING_STATUSES:
        pending.status = "expired"
        return pending_id

    if pending.status in RETIRED_PENDING_STATUSES:
        return pending_id

    return None


def _execution_retention_anchor(
    row: WorkflowProposal,
) -> Optional[datetime]:
    """Return the absolute retry/retention anchor for an execution row.

    ``updated_at`` is intentionally excluded. Retry attempts and status
    polling must never extend transient-document retention indefinitely.
    """

    return row.approved_at or row.created_at


def _retire_stale_document_execution(
    session,
    row: WorkflowProposal,
    now: datetime,
) -> Optional[str]:
    """Retire one stale execution workflow in the caller's transaction."""

    row.status = "EXPIRED"
    row.updated_at = now
    if not str(row.last_error or "").strip():
        row.last_error = (
            "Document execution retention expired before completion."
        )

    pending_id = str(row.pending_document_id or "").strip()
    if not pending_id:
        return None

    pending = session.get(PendingDocumentUpload, pending_id)
    if pending is None:
        return None

    cleanup_eligible_statuses = (
        ACTIVE_REVIEW_PENDING_STATUSES
        + PROTECTED_PENDING_STATUSES
        + RETIRED_PENDING_STATUSES
    )
    if pending.status not in cleanup_eligible_statuses:
        return None

    if pending.status not in RETIRED_PENDING_STATUSES:
        pending.status = "expired"

    return pending_id


def cleanup_terminal_pending_upload(
    pending_id: str,
) -> Dict[str, Any]:
    """Remove transient content for one already-retired pending upload.

    This function is idempotent.  It never changes an active/protected pending
    row into a terminal state.  The DB state transition must happen first.
    """

    pending_key = str(pending_id or "").strip()
    if not pending_key:
        return {
            "status": "skipped",
            "reason": "missing_pending_id",
        }

    session = SessionLocal()

    try:
        pending = session.get(PendingDocumentUpload, pending_key)
        if pending is None:
            return {
                "status": "not_found",
                "binary_deleted": False,
                "ocr_cleared": False,
            }

        if pending.status not in RETIRED_PENDING_STATUSES:
            return {
                "status": "skipped",
                "reason": "pending_status_not_retired",
                "pending_status": pending.status,
            }

        temp_path = str(pending.temp_path or "")
        binary_deleted = _delete_pending_binary(temp_path)

        ocr_cleared = pending.extracted_text is not None
        pending.extracted_text = None

        # Keep hashes/classification/audit state, but remove the stale local
        # file pointer once the file is confirmed absent.
        if binary_deleted:
            pending.temp_path = ""

        session.commit()

        return {
            "status": "cleaned",
            "pending_status": pending.status,
            "binary_deleted": binary_deleted,
            "ocr_cleared": ocr_cleared,
        }

    except Exception:
        session.rollback()
        logger.exception("Pending-document terminal cleanup failed.")
        return {
            "status": "failed",
            "binary_deleted": False,
            "ocr_cleared": False,
        }
    finally:
        session.close()


def cleanup_expired_pending_documents(
    now: Optional[datetime] = None,
    ttl_hours: int = PENDING_DOCUMENT_TTL_HOURS,
    execution_retention_hours: int = DOCUMENT_EXECUTION_RETENTION_HOURS,
    batch_size: int = 200,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Expire abandoned reviews and clean retired staged-document content.

    ``dry_run=True`` performs no DB writes and no file deletion.  The sweep is
    intentionally bounded so it can later be run from a scheduler without a
    large one-shot transaction.
    """

    now = now or utcnow()
    ttl_hours = max(1, int(ttl_hours))
    execution_retention_hours = max(
        1,
        int(execution_retention_hours),
    )
    batch_size = max(1, int(batch_size))
    cutoff = now - timedelta(hours=ttl_hours)
    execution_cutoff = now - timedelta(
        hours=execution_retention_hours
    )

    session = SessionLocal()
    cleanup_ids: Set[str] = set()

    stats: Dict[str, Any] = {
        "dry_run": bool(dry_run),
        "ttl_hours": ttl_hours,
        "execution_retention_hours": execution_retention_hours,
        "expired_workflows": 0,
        "retired_stale_executions": 0,
        "expired_orphan_pending": 0,
        "repaired_terminal_pending": 0,
        "terminal_cleanup_candidates": 0,
        "cleaned_rows": 0,
        "binary_delete_failures": 0,
        "cleanup_failures": 0,
    }

    try:
        workflow_rows = (
            session.query(WorkflowProposal)
            .filter(
                WorkflowProposal.kind.in_(DOCUMENT_WORKFLOW_KINDS),
                WorkflowProposal.status == "AWAITING_REVIEW",
                WorkflowProposal.expires_at.isnot(None),
            )
            .order_by(WorkflowProposal.expires_at.asc())
            .limit(batch_size)
            .all()
        )

        for row in workflow_rows:
            if not _is_expired(row.expires_at, now):
                continue

            stats["expired_workflows"] += 1
            pending_id = str(row.pending_document_id or "").strip()

            if dry_run:
                if pending_id:
                    cleanup_ids.add(pending_id)
                continue

            cleanup_id = mark_document_review_expired(
                session,
                row,
                now=now,
            )
            if cleanup_id:
                cleanup_ids.add(cleanup_id)

        execution_rows = (
            session.query(WorkflowProposal)
            .filter(
                WorkflowProposal.kind.in_(DOCUMENT_WORKFLOW_KINDS),
                WorkflowProposal.status.in_(
                    RECOVERABLE_DOCUMENT_WORKFLOW_STATUSES
                ),
            )
            .order_by(
                func.coalesce(
                    WorkflowProposal.approved_at,
                    WorkflowProposal.created_at,
                ).asc()
            )
            .limit(batch_size)
            .all()
        )

        for row in execution_rows:
            anchor = _execution_retention_anchor(row)
            if not _is_older_than(anchor, execution_cutoff):
                continue

            stats["retired_stale_executions"] += 1
            pending_id = str(row.pending_document_id or "").strip()

            if dry_run:
                if pending_id:
                    cleanup_ids.add(pending_id)
                continue

            cleanup_id = _retire_stale_document_execution(
                session,
                row,
                now,
            )
            if cleanup_id:
                cleanup_ids.add(cleanup_id)

        active_pending_rows = (
            session.query(PendingDocumentUpload)
            .filter(
                PendingDocumentUpload.status.in_(
                    ACTIVE_REVIEW_PENDING_STATUSES
                )
            )
            .order_by(PendingDocumentUpload.created_at.asc())
            .limit(batch_size)
            .all()
        )

        for pending in active_pending_rows:
            pending_key = str(pending.pending_id)
            if pending_key in cleanup_ids:
                continue

            if not _is_older_than(pending.created_at, cutoff):
                continue

            latest_workflow = (
                session.query(WorkflowProposal)
                .filter(
                    WorkflowProposal.kind.in_(DOCUMENT_WORKFLOW_KINDS),
                    WorkflowProposal.pending_document_id
                    == pending.pending_id,
                )
                .order_by(
                    WorkflowProposal.updated_at.desc(),
                    WorkflowProposal.created_at.desc(),
                )
                .first()
            )

            if latest_workflow is None:
                stats["expired_orphan_pending"] += 1
                cleanup_ids.add(str(pending.pending_id))
                if not dry_run:
                    pending.status = "expired"
                continue

            if latest_workflow.status == "AWAITING_REVIEW":
                # A recent edit can extend proposal.expires_at even when the
                # original PendingDocumentUpload.created_at is old.
                if not _is_expired(latest_workflow.expires_at, now):
                    continue

                stats["expired_workflows"] += 1
                cleanup_ids.add(str(pending.pending_id))
                if not dry_run:
                    mark_document_review_expired(
                        session,
                        latest_workflow,
                        now=now,
                    )
                continue

            mapped_status = _WORKFLOW_TO_PENDING_TERMINAL_STATUS.get(
                latest_workflow.status
            )
            if mapped_status:
                stats["repaired_terminal_pending"] += 1
                cleanup_ids.add(str(pending.pending_id))
                if not dry_run:
                    pending.status = mapped_status
                continue

            # Recent APPROVED / EXECUTING / FAILED rows remain protected.
            # Stale rows are retired by the bounded execution sweep above.

        terminal_rows = (
            session.query(PendingDocumentUpload)
            .filter(
                PendingDocumentUpload.status.in_(RETIRED_PENDING_STATUSES),
                or_(
                    PendingDocumentUpload.extracted_text.isnot(None),
                    PendingDocumentUpload.temp_path != "",
                ),
            )
            .order_by(PendingDocumentUpload.created_at.asc())
            .limit(batch_size)
            .all()
        )

        for pending in terminal_rows:
            cleanup_ids.add(str(pending.pending_id))

        stats["terminal_cleanup_candidates"] = len(cleanup_ids)

        if dry_run:
            session.rollback()
            return stats

        session.commit()

    except Exception:
        session.rollback()
        logger.exception("Pending-document lifecycle sweep failed.")
        raise
    finally:
        session.close()

    for pending_id in sorted(cleanup_ids):
        result = cleanup_terminal_pending_upload(pending_id)
        if result.get("status") == "cleaned":
            stats["cleaned_rows"] += 1
            if not result.get("binary_deleted", False):
                stats["binary_delete_failures"] += 1
        elif result.get("status") == "failed":
            stats["cleanup_failures"] += 1

    return stats
