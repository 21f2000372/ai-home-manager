"""Service layer for household members, invites, and role management."""
from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, verify_password
from app.models.enums import HouseholdRole, InviteStatus, MembershipStatus
from app.models.people import Invite, Membership, User


class PeopleService:
    @staticmethod
    def _hash_code(code: str) -> str:
        return hashlib.sha256(code.encode("utf-8")).hexdigest()

    @classmethod
    def register_initial_admin(
        cls,
        session: Session,
        email: str,
        password: str,
        display_name: str,
        date_of_birth: Optional[date] = None,
    ) -> Tuple[User, str]:
        """Registers the initial user as an Admin (US-1.1).

        Fails if any active members already exist in the single household.
        """
        existing_user = session.query(User).filter(User.email == email.lower()).first()
        if existing_user:
            raise ValueError("Email already registered")

        active_count = (
            session.query(func.count(Membership.membership_id))
            .filter(Membership.status == MembershipStatus.ACTIVE)
            .scalar()
        )
        if active_count and active_count > 0:
            raise ValueError("Household already initialized. Must join via invite.")

        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            display_name=display_name,
            date_of_birth=date_of_birth,
        )
        user.membership = Membership(
            role=HouseholdRole.ADMIN,
            status=MembershipStatus.ACTIVE,
        )
        session.add(user)
        session.commit()
        return user, "Household created and admin assigned."

    @classmethod
    def authenticate(
        cls, session: Session, email: str, password: str
    ) -> Optional[User]:
        """Verify user credentials and active membership status."""
        user = session.query(User).filter(User.email == email.lower()).first()
        if not user or not verify_password(password, user.password_hash):
            print(user)
            return None
        
        return user

    @classmethod
    def create_invite(
        cls, session: Session, created_by_id: str, days_valid: int = 7
    ) -> str:
        """Create a cryptographically secure, hashed invite token (US-1.2)."""
        raw_code = secrets.token_urlsafe(16)
        code_hash = cls._hash_code(raw_code)

        invite = Invite(
            code_hash=code_hash,
            status=InviteStatus.ACTIVE,
            expires_at=datetime.now(timezone.utc) + timedelta(days=days_valid),
            created_by=created_by_id,
        )
        session.add(invite)
        session.commit()
        return raw_code

    @classmethod
    def register_with_invite(
        cls,
        session: Session,
        invite_code: str,
        email: str,
        password: str,
        display_name: str,
        date_of_birth: Optional[date] = None,
    ) -> User:
        """Join household via invite code in PENDING status (US-1.2)."""
        code_hash = cls._hash_code(invite_code)
        now = datetime.now()

        invite = (
            session.query(Invite)
            .filter(Invite.code_hash == code_hash, Invite.status == InviteStatus.ACTIVE)
            .first()
        )
        if not invite:
            raise ValueError("Invalid invite code")

        if invite.expires_at and invite.expires_at < now:
            invite.status = InviteStatus.EXPIRED
            session.commit()
            raise ValueError("Invite code has expired")

        existing_user = session.query(User).filter(User.email == email.lower()).first()
        if existing_user:
            raise ValueError("Email already in use")

        user = User(
            email=email.lower(),
            password_hash=hash_password(password),
            display_name=display_name,
            date_of_birth=date_of_birth,
        )
        # Assigned GUEST role by default pending admin review
        user.membership = Membership(
            role=HouseholdRole.GUEST,
            status=MembershipStatus.PENDING,
        )

        session.add(user)
        session.commit()
        return user

    @classmethod
    def approve_member(
        cls, session: Session, target_user_id: str, role: HouseholdRole
    ) -> Membership:
        """Admin approves a pending member and assigns their role (US-1.3)."""
        membership = (
            session.query(Membership)
            .filter(Membership.user_id == target_user_id)
            .first()
        )
        if not membership:
            raise ValueError("Membership record not found")
        if membership.status != MembershipStatus.PENDING:
            raise ValueError("Only pending members can be approved")

        membership.role = role
        membership.status = MembershipStatus.ACTIVE
        session.commit()
        return membership

    @classmethod
    def change_member_role(
        cls, session: Session, target_user_id: str, new_role: HouseholdRole
    ) -> Membership:
        """Update a member's role with admin demotion guardrails (US-1.4)."""
        membership = (
            session.query(Membership)
            .filter(Membership.user_id == target_user_id)
            .first()
        )
        if not membership:
            raise ValueError("Membership not found")

        # Guard: Cannot demote the last remaining admin
        if membership.role == HouseholdRole.ADMIN and new_role != HouseholdRole.ADMIN:
            admin_count = (
                session.query(func.count(Membership.membership_id))
                .filter(
                    Membership.role == HouseholdRole.ADMIN,
                    Membership.status == MembershipStatus.ACTIVE,
                )
                .scalar()
            )
            if admin_count <= 1:
                raise ValueError("Cannot demote the sole household Admin.")

        membership.role = new_role
        session.commit()
        return membership

    @classmethod
    def transfer_admin(
        cls, session: Session, current_admin_id: str, successor_user_id: str
    ) -> None:
        """Transfer sole ownership to another Adult (US-1.5)."""
        current_admin = (
            session.query(Membership)
            .filter(Membership.user_id == current_admin_id)
            .first()
        )
        successor = (
            session.query(Membership)
            .filter(Membership.user_id == successor_user_id)
            .first()
        )

        if not successor or successor.status != MembershipStatus.ACTIVE:
            raise ValueError("Successor must be an active household member")
        if successor.role != HouseholdRole.ADULT:
            raise ValueError("Admin duties can only be transferred to an Adult")

        successor.role = HouseholdRole.ADMIN
        current_admin.role = HouseholdRole.ADULT
        session.commit()