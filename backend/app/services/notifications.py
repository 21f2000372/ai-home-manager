from __future__ import annotations

from typing import List
from sqlalchemy.orm import Session
from app.models.notifications import Notification

class NotificationService:
    @staticmethod
    def create_notification(
        session: Session,
        user_id: str,
        title: str,
        message: str,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            title=title.strip(),
            message=message.strip(),
        )
        session.add(notification)
        session.commit()
        return notification

    @staticmethod
    def list_user_notifications(
        session: Session,
        user_id: str,
        unread_only: bool = False,
        limit: int = 20,
    ) -> List[Notification]:
        query = session.query(Notification).filter(Notification.user_id == user_id)
        if unread_only:
            query = query.filter(Notification.read.is_(False))
        return query.order_by(Notification.created_at.desc()).limit(limit).all()

    @staticmethod
    def mark_as_read(session: Session, notification_id: str, user_id: str) -> Notification:
        notif = (
            session.query(Notification)
            .filter(
                Notification.notification_id == notification_id,
                Notification.user_id == user_id,
            )
            .first()
        )
        if not notif:
            raise ValueError("Notification not found")
        notif.read = True
        session.commit()
        return notif

    @staticmethod
    def mark_all_as_read(session: Session, user_id: str) -> int:
        count = (
            session.query(Notification)
            .filter(Notification.user_id == user_id, Notification.read.is_(False))
            .update({"read": True})
        )
        session.commit()
        return count