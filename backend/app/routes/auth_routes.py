"""Authentication and membership API endpoints."""
from __future__ import annotations

from datetime import date
from flask import Blueprint, g, jsonify, request

from app.auth.decorators import login_required, require_role
from app.auth.jwt import create_access_token
from app.db.base import SessionLocal
from app.models.enums import HouseholdRole, MembershipStatus
from app.models.people import Membership, User
from app.services.people import PeopleService

auth_bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@auth_bp.route("/register-household", methods=["POST"])
def register_household():
    """US-1.1: Register initial user as Admin."""
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")
    display_name = data.get("display_name")
    dob_str = data.get("date_of_birth")

    if not email or not password or not display_name:
        return jsonify({"error": "email, password, and display_name are required"}), 400

    dob = date.fromisoformat(dob_str) if dob_str else None

    session = SessionLocal()
    try:
        user, _ = PeopleService.register_initial_admin(
            session, email, password, display_name, dob
        )
        token = create_access_token(user.user_id, user.email, user.membership.role)
        return jsonify({
            "message": "Household created",
            "token": token,
            "user": {
                "id": user.user_id,
                "email": user.email,
                "role": user.membership.role.value,
            },
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate and issue JWT token."""
    data = request.get_json() or {}
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    session = SessionLocal()
    try:
        user = PeopleService.authenticate(session, email, password)
        print(user)
        if not user or not user.membership:
            # print(user.membership)
            return jsonify({"error": "Invalid email or password"}), 401

        if user.membership.status != MembershipStatus.ACTIVE:
            return jsonify({"error": "Membership pending approval by household Admin"}), 403

        token = create_access_token(user.user_id, user.email, user.membership.role)
        return jsonify({
            "token": token,
            "user": {
                "id": user.user_id,
                "email": user.email,
                "name": user.display_name,
                "role": user.membership.role.value,
            },
        }), 200
    finally:
        session.close()


@auth_bp.route("/invite", methods=["POST"])
@require_role(HouseholdRole.ADMIN)
def create_invite():
    """US-1.2: Admin generates an invitation code."""
    session = SessionLocal()
    try:
        code = PeopleService.create_invite(session, g.current_user.user_id)
        return jsonify({"invite_code": code}), 201
    finally:
        session.close()


@auth_bp.route("/join", methods=["POST"])
def join_household():
    """US-1.2: Register an account using an invite code."""
    data = request.get_json() or {}
    invite_code = data.get("invite_code")
    email = data.get("email")
    password = data.get("password")
    display_name = data.get("display_name")
    dob_str = data.get("date_of_birth")

    if not all([invite_code, email, password, display_name]):
        return jsonify({"error": "Missing required fields"}), 400

    dob = date.fromisoformat(dob_str) if dob_str else None

    session = SessionLocal()
    try:
        user = PeopleService.register_with_invite(
            session, invite_code, email, password, display_name, dob
        )
        return jsonify({
            "message": "Registration successful. Awaiting Admin approval.",
            "user_id": user.user_id,
        }), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@auth_bp.route("/members/pending", methods=["GET"])
@require_role(HouseholdRole.ADMIN)
def get_pending_members():
    """US-1.3: Admin view for reviewing pending members."""
    session = SessionLocal()
    try:
        pending = (
            session.query(User)
            .join(Membership)
            .filter(Membership.status == MembershipStatus.PENDING)
            .all()
        )
        return jsonify([
            {
                "user_id": u.user_id,
                "name": u.display_name,
                "email": u.email,
                "date_of_birth": u.date_of_birth.isoformat() if u.date_of_birth else None,
            }
            for u in pending
        ]), 200
    finally:
        session.close()


@auth_bp.route("/members/<string:user_id>/approve", methods=["POST"])
@require_role(HouseholdRole.ADMIN)
def approve_member(user_id: str):
    """US-1.3: Admin approves pending member and assigns role."""
    data = request.get_json() or {}
    role_str = data.get("role")

    try:
        role = HouseholdRole(role_str)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid role specified"}), 400

    session = SessionLocal()
    try:
        PeopleService.approve_member(session, user_id, role)
        return jsonify({"message": f"User approved as {role.value}"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@auth_bp.route("/members/<string:user_id>/role", methods=["PUT"])
@require_role(HouseholdRole.ADMIN)
def change_role(user_id: str):
    """US-1.4: Update role of an active member."""
    data = request.get_json() or {}
    role_str = data.get("role")

    try:
        new_role = HouseholdRole(role_str)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid role specified"}), 400

    session = SessionLocal()
    try:
        PeopleService.change_member_role(session, user_id, new_role)
        return jsonify({"message": "Role updated successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()


@auth_bp.route("/transfer-admin", methods=["POST"])
@require_role(HouseholdRole.ADMIN)
def transfer_admin():
    """US-1.5: Transfer Admin rights to an Adult member."""
    data = request.get_json() or {}
    successor_id = data.get("successor_id")

    if not successor_id:
        return jsonify({"error": "successor_id is required"}), 400

    session = SessionLocal()
    try:
        PeopleService.transfer_admin(session, g.current_user.user_id, successor_id)
        return jsonify({"message": "Admin privileges transferred successfully"}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    finally:
        session.close()