"""Documents + Conversation/Memory domain models (US-6.x).

Documents store uploaded receipts/bills/warranties. The binary lives in object
storage; only metadata + a storage key live here.

PendingDocumentUpload stores temporary staged-document metadata before the user
confirms the proposed actions.

A document can link to one or more domain records via ``document_links``.

Conversation + AgentInteraction back the orchestrator's short-term memory and
provide records that the RAG layer can embed and retrieve later.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, _uuid_str, utcnow
from app.models.enums import DocumentType


class Document(Base):
    """
    Permanent metadata for an approved uploaded document.

    The binary itself is stored in private object storage. This table stores
    metadata, duplicate fingerprints, extracted text, classification details,
    and the private storage reference.
    """

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )

    document_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            native_enum=False,
            length=20,
        ),
        nullable=False,
        default=DocumentType.OTHER,
    )

    # Detailed classifier output, for example:
    # GroceryReceipt, UtilityBill, Warranty, RepairInvoice.
    classified_document_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    domain: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )

    classification_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    classification_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Private object-storage key.
    # For Cloudinary this can hold the Cloudinary public_id.
    storage_key: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )

    original_filename: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    mime_type: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    extension: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Duplicate detection fingerprints
    # ------------------------------------------------------------------

    sha256: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    normalized_text_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    # JSON-encoded list of perceptual hashes.
    visual_hashes_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    extraction_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=1,
    )

    # ------------------------------------------------------------------
    # Security / lifecycle
    # ------------------------------------------------------------------

    prompt_injection_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="approved",
        index=True,
    )

    uploaded_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    links: Mapped[list["DocumentLink"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<Document "
            f"{self.document_type.value} "
            f"{self.original_filename}>"
        )


class PendingDocumentUpload(Base):
    """
    Temporary metadata for a staged upload awaiting confirmation.

    The original binary remains in ``.pending_uploads`` while the user reviews
    the extracted data and proposed actions.

    Only after confirmation should the file be moved to permanent object
    storage and converted into a permanent Document row.
    """

    __tablename__ = "pending_document_uploads"

    pending_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )

    upload_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        unique=True,
        index=True,
    )

    uploaded_by: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    safe_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    temp_path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    mime_type: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    extension: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    file_size: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Duplicate detection fingerprints
    # ------------------------------------------------------------------

    sha256: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    normalized_text_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    visual_hashes_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # OCR / text extraction
    # ------------------------------------------------------------------

    extracted_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    extraction_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        default=1,
    )

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    domain: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
        index=True,
    )

    classified_document_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    classification_confidence: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
    )

    classification_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Guardrails / review
    # ------------------------------------------------------------------

    prompt_injection_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    status: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        default="staged",
        index=True,
    )

    # JSON-encoded list of review messages.
    review_reasons_json: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    def __repr__(self) -> str:
        return (
            f"<PendingDocumentUpload "
            f"{self.upload_id} "
            f"{self.status}>"
        )


class DocumentLink(Base):
    """
    Polymorphic link from a document to an owning domain record.

    ``linked_domain`` is an allow-listed string such as ``finance``,
    ``maintenance`` or ``inventory``.

    One document can create several domain records.
    """

    __tablename__ = "document_links"

    __table_args__ = (
        UniqueConstraint(
            "linked_domain",
            "linked_record_id",
            name="uq_document_link_domain_record",
        ),
    )

    link_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )

    document_id: Mapped[str] = mapped_column(
        ForeignKey(
            "documents.document_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    linked_domain: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    linked_record_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    document: Mapped["Document"] = relationship(
        back_populates="links",
    )

    def __repr__(self) -> str:
        return (
            f"<DocumentLink "
            f"{self.linked_domain}:"
            f"{self.linked_record_id}>"
        )


class Conversation(Base):
    """
    A chat session grouping a series of agent interactions.
    """

    __tablename__ = "conversations"

    conversation_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )

    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    interactions: Mapped[list["AgentInteraction"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )


class AgentInteraction(Base):
    """
    One request/response turn persisted for memory and RAG.

    Embeddings are stored separately in Chroma and can reference this
    interaction's ID.
    """

    __tablename__ = "agent_interactions"

    interaction_id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
    )

    conversation_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "conversations.conversation_id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    session_id: Mapped[str] = mapped_column(
        String(36),
        nullable=False,
        index=True,
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.user_id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    intent: Mapped[Optional[str]] = mapped_column(
        String(120),
        nullable=True,
    )

    message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    response: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
    )

    conversation: Mapped[Optional["Conversation"]] = relationship(
        back_populates="interactions",
    )

    def __repr__(self) -> str:
        return (
            f"<AgentInteraction "
            f"{self.intent}>"
        )