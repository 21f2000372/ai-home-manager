from __future__ import annotations

from flask import Blueprint, g, jsonify, request
from app.auth.decorators import login_required
from app.db.base import SessionLocal
from app.services.notifications import NotificationService

notification_bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")

@notification_bp.route("", methods=["GET", "OPTIONS"])
@login_required
def get_notifications():
    if request.method == "OPTIONS":
        return ("", 200)

    unread_only = request.args.get("unread_only", "false").lower() == "true"
    session = SessionLocal()
    try:
        notifs = NotificationService.list_user_notifications(
            session=session,
            user_id=g.current_user.user_id,
            unread_only=unread_only,
        )
        return jsonify([
            {
                "notification_id": n.notification_id,
                "title": n.title,
                "message": n.message,
                "read": n.read,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifs
        ]), 200
    finally:
        session.close()

@notification_bp.route("/<string:notification_id>/read", methods=["PATCH", "OPTIONS"])
@login_required
def mark_read(notification_id: str):
    if request.method == "OPTIONS":
        return ("", 200)

    session = SessionLocal()
    try:
        notif = NotificationService.mark_as_read(
            session=session,
            notification_id=notification_id,
            user_id=g.current_user.user_id,
        )
        return jsonify({"message": "Marked as read", "notification_id": notif.notification_id}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    finally:
        session.close()

@notification_bp.route("/read-all", methods=["PATCH", "OPTIONS"])
@login_required
def mark_all_read():
    if request.method == "OPTIONS":
        return ("", 200)

    session = SessionLocal()
    try:
        count = NotificationService.mark_all_as_read(session=session, user_id=g.current_user.user_id)
        return jsonify({"message": "All notifications marked as read", "count": count}), 200
    finally:
        session.close()