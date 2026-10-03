"""Read-only API for approved documents and the caller's pending uploads."""
from __future__ import annotations

from pathlib import Path

from flask import Blueprint, g, jsonify, send_file
from itsdangerous import BadSignature, SignatureExpired

from app.auth.decorators import login_required
from app.config import config
from app.db.base import SessionLocal
from app.models.documents import Document, PendingDocumentUpload
from app.models.enums import HouseholdRole, MembershipStatus
from app.models.people import User
from app.rag.document_access import can_read_document
from app.rag.document_retrieval import DocumentRetrievalError, get_original_document
from app.services.document_lifecycle import (
    ACTIVE_REVIEW_PENDING_STATUSES,
    PROTECTED_PENDING_STATUSES,
)
from app.services.document_reads import DocumentReadService
from app.storage.document_storage import load_local_view_token, pending_view_url
from app.storage.local_storage import resolve_local_document
from app.storage.temp_storage import get_temp_upload_dir


documents_bp = Blueprint("documents", __name__, url_prefix="/api/documents")
VIEWABLE_PENDING_STATUSES = (
    ACTIVE_REVIEW_PENDING_STATUSES + PROTECTED_PENDING_STATUSES
)


@documents_bp.route("", methods=["GET", "OPTIONS"])
@login_required
def list_documents():
    session = SessionLocal()
    try:
        result = DocumentReadService.list_for_user(
            session=session,
            user_id=g.current_user.user_id,
            role=g.current_role,
        )
        return jsonify(result), 200
    finally:
        session.close()


@documents_bp.route("/<string:document_id>/view", methods=["GET", "OPTIONS"])
@login_required
def view_document(document_id: str):
    if g.current_role == HouseholdRole.GUEST:
        return jsonify({"error": "You do not have permission to view original documents."}), 403

    try:
        document = get_original_document(
            role=g.current_role.value,
            document_reference=document_id,
            user_id=g.current_user.user_id,
            inline_view=True,
        )
        return jsonify(document), 200
    except DocumentRetrievalError as exc:
        return jsonify({"error": str(exc)}), exc.status_code


@documents_bp.route("/pending/<string:pending_id>/view", methods=["GET", "OPTIONS"])
@login_required
def view_pending_document(pending_id: str):
    session = SessionLocal()
    try:
        pending = session.get(PendingDocumentUpload, pending_id)
        if pending is None or pending.uploaded_by != g.current_user.user_id:
            return jsonify({"error": "Pending document is unavailable."}), 404
        if pending.status not in VIEWABLE_PENDING_STATUSES:
            return jsonify({"error": "Pending document is no longer available for review."}), 404

        return jsonify({
            "view_url": pending_view_url(
                pending_id=pending.pending_id,
                user_id=g.current_user.user_id,
            )
        }), 200
    finally:
        session.close()


@documents_bp.route("/local-file/<string:token>", methods=["GET"])
def serve_local_document(token: str):
    try:
        payload = load_local_view_token(token)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return jsonify({"error": "Document view link is invalid or expired."}), 403

    session = SessionLocal()
    try:
        kind = payload.get("kind")
        if kind == "document":
            document = session.get(Document, payload.get("document_id"))
            if (
                document is None
                or document.status != "approved"
                or document.prompt_injection_detected
                or document.storage_key != payload.get("storage_key")
            ):
                return jsonify({"error": "Document is unavailable."}), 404

            role_value = payload.get("role")
            user_id = payload.get("user_id")
            if user_id:
                user = session.get(User, user_id)
                if (
                    user is None
                    or user.membership is None
                    or user.membership.status != MembershipStatus.ACTIVE
                ):
                    return jsonify({"error": "Document access is no longer available."}), 403
                role_value = user.membership.role
            try:
                role = HouseholdRole(role_value)
            except Exception:
                return jsonify({"error": "Document access is no longer available."}), 403
            if not can_read_document(role, document):
                return jsonify({"error": "You do not have permission to view this document."}), 403

            path = resolve_local_document(document.storage_key)
            filename = document.original_filename or "document"
            mime_type = document.mime_type or "application/octet-stream"
            inline = bool(payload.get("inline", True))
        elif kind == "pending":
            pending = session.get(PendingDocumentUpload, payload.get("pending_id"))
            user = session.get(User, payload.get("user_id"))
            if (
                pending is None
                or pending.uploaded_by != payload.get("user_id")
                or pending.status not in VIEWABLE_PENDING_STATUSES
                or user is None
                or user.membership is None
                or user.membership.status != MembershipStatus.ACTIVE
            ):
                return jsonify({"error": "Pending document is unavailable."}), 404
            root = get_temp_upload_dir().resolve()
            path = Path(pending.temp_path).resolve()
            if path == root or root not in path.parents or not path.is_file():
                return jsonify({"error": "Pending document file is unavailable."}), 404
            filename = pending.original_filename
            mime_type = pending.mime_type or "application/octet-stream"
            inline = True
        else:
            return jsonify({"error": "Document view link is invalid."}), 403

        return send_file(
            path,
            mimetype=mime_type,
            as_attachment=not inline,
            download_name=filename,
            conditional=True,
        )
    except (FileNotFoundError, ValueError):
        return jsonify({"error": "Document file is unavailable."}), 404
    finally:
        session.close()