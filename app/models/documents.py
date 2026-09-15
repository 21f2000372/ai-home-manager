"""Documents + Conversation/Memory domain models (US-6.x).

Documents store uploaded receipts/bills/warranties (binary lives in object
storage; only metadata + a storage key live here). A document can link to one
or more domain records via ``document_links`` (many-links model).

Conversation + AgentInteraction back the orchestrator's short-term memory and
provide records that the RAG layer can embed and retrieve later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _uuid_str, utcnow
from app.models.enums import DocumentType


class Document(Base):
    """Metadata + private storage reference for an uploaded file (US-6.1)."""

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    document_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, native_enum=False, length=12),
        nullable=False,
        default=DocumentType.OTHER,
    )
    # Key into private object storage; the binary is never stored in the DB.
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    uploaded_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    links: Mapped[list["DocumentLink"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Document {self.document_type.value} {self.original_filename}>"


class DocumentLink(Base):
    """Polymorphic link from a document to an owning domain record.

    ``linked_domain`` is an allow-listed string (e.g. "finance", "maintenance")
    and ``linked_record_id`` is that record's id. One document can have many
    links, but a given (domain, record) is linked at most once.
    """

    __tablename__ = "document_links"
    __table_args__ = (
        UniqueConstraint(
            "linked_domain", "linked_record_id", name="uq_document_link_domain_record"
        ),
    )

    link_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.document_id", ondelete="CASCADE"), nullable=False, index=True
    )
    linked_domain: Mapped[str] = mapped_column(String(40), nullable=False)
    linked_record_id: Mapped[str] = mapped_column(String(36), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped["Document"] = relationship(back_populates="links")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<DocumentLink {self.linked_domain}:{self.linked_record_id}>"


class Conversation(Base):
    """A chat session grouping a series of agent interactions (US-6.3)."""

    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    interactions: Mapped[list["AgentInteraction"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class AgentInteraction(Base):
    """One request/response turn persisted for memory and RAG (US-6.3).

    Keyed by conversation/session/user. ``intent`` and ``response`` are the
    minimal fields the orchestrator references; embeddings for RAG are stored
    in the Chroma vector store and reference this row's id.
    """

    __tablename__ = "agent_interactions"

    interaction_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    conversation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("conversations.conversation_id", ondelete="CASCADE"), nullable=True, index=True
    )
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True
    )
    intent: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped[Optional["Conversation"]] = relationship(back_populates="interactions")

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<AgentInteraction {self.intent}>"
