"""Durable workflow proposal and execution-ledger models.

These tables make approval state durable across process restarts and provide
idempotency for side-effecting operations.

Compatibility target: Python 3.8+.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _uuid_str, utcnow


class WorkflowProposal(Base):
    """Persisted proposal awaiting review or execution.

    The database row is the source of truth for what the user reviewed and
    approved. LangGraph/checkpointer state may reference this row, but must not
    be the only durable copy of the proposal.

    ``payload_json`` stores the exact serialized proposal revision shown to the
    user. ``args_hash`` binds approval to that exact revision/argument set.
    """

    __tablename__ = "workflow_proposals"

    proposal_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )

    # Session is always present in the current agent runtime and is the primary
    # lookup key used when the user later replies "yes" or "no".
    session_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    conversation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "conversations.conversation_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # Examples: document, duplicate, conflict, action.
    kind: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        default="action",
        index=True,
    )

    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )

    # Exact JSON presented for review. Application code, not the LLM, restores
    # this payload after confirmation.
    payload_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # SHA-256 hex digest of the canonical approved action arguments/proposal.
    # Any edit must increment revision and update this hash.
    args_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    pending_document_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "pending_document_uploads.pending_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # DRAFT | AWAITING_REVIEW | APPROVED | REJECTED | EXECUTING |
    # COMPLETED | FAILED | CANCELLED | EXPIRED
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="AWAITING_REVIEW",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    approved_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    last_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    executions: Mapped[List["ExecutionLedger"]] = relationship(
        back_populates="proposal",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            "revision",
            name="uq_workflow_proposal_revision",
        ),
    )

    def __repr__(self) -> str:
        return (
            "<WorkflowProposal "
            + self.proposal_id
            + " "
            + self.kind
            + " "
            + self.status
            + ">"
        )


class ExecutionLedger(Base):
    """One durable execution record for one proposal action.

    ``idempotency_key`` is globally unique. Before a side effect is attempted,
    application code must insert/load this row and avoid re-running an action
    that has already completed for the same proposal revision and action index.
    """

    __tablename__ = "execution_ledger"

    execution_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )

    proposal_id: Mapped[str] = mapped_column(
        ForeignKey(
            "workflow_proposals.proposal_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    revision: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    action_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        index=True,
    )

    operation: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
        index=True,
    )

    arguments_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # PENDING | RUNNING | COMPLETED | FAILED | SKIPPED
    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="PENDING",
        index=True,
    )

    result_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    proposal: Mapped["WorkflowProposal"] = relationship(
        back_populates="executions",
    )

    __table_args__ = (
        UniqueConstraint(
            "proposal_id",
            "revision",
            "action_index",
            name="uq_execution_proposal_revision_action",
        ),
    )

    def __repr__(self) -> str:
        return (
            "<ExecutionLedger "
            + self.execution_id
            + " "
            + self.operation
            + " "
            + self.status
            + ">"
        )
