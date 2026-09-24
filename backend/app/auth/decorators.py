"""Flask decorators for JWT verification and role-based access control (RBAC)."""
from __future__ import annotations

from functools import wraps
from typing import Callable, Iterable

from flask import g, jsonify, request
import jwt

from app.auth.jwt import decode_access_token
from app.db.base import SessionLocal
from app.models import Membership, MembershipStatus, User
from app.models.enums import HouseholdRole

# Role privilege hierarchy for threshold authorization checks
ROLE_HIERARCHY: dict[HouseholdRole, int] = {
    HouseholdRole.GUEST: 0,
    HouseholdRole.CHILD: 1,
    HouseholdRole.ADULT: 2,
    HouseholdRole.ADMIN: 3,
}


def login_required(f: Callable) -> Callable:
    """Validate Bearer token and populate flask.g with the authenticated user."""
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if request.method == "OPTIONS":
            return ("", 200)
        
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or malformed Authorization header"}), 401

        token = auth_header.split(" ", 1)[1].strip()
        try:
            payload = decode_access_token(token)
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token has expired"}), 401
        except jwt.PyJWTError:
            return jsonify({"error": "Invalid token"}), 401

        session = SessionLocal()
        try:
            user = (
                session.query(User)
                .filter(User.user_id == payload["sub"])
                .first()
            )
            if not user or not user.membership:
                return jsonify({"error": "User account or membership not found"}), 401

            if user.membership.status != MembershipStatus.ACTIVE:
                return jsonify({"error": "User membership is pending or suspended"}), 403

            # Store on Flask context
            g.current_user = user
            g.current_role = user.membership.role
            return f(*args, **kwargs)
        finally:
            session.close()

    return decorated_function


def require_role(*allowed_roles: HouseholdRole) -> Callable:
    """Ensure current user matches one of the specified roles (e.g. Admin only)."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            if request.method == "OPTIONS":
                return f(*args, **kwargs)
            
            if g.current_role not in allowed_roles:
                return jsonify({
                    "error": "Forbidden: insufficient role permissions",
                    "required_roles": [r.value for r in allowed_roles],
                }), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


def require_min_role(min_role: HouseholdRole) -> Callable:
    """Ensure the user's role meets or exceeds a given privilege level in the hierarchy."""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            user_level = ROLE_HIERARCHY.get(g.current_role, 0)
            required_level = ROLE_HIERARCHY.get(min_role, 0)

            if user_level < required_level:
                return jsonify({
                    "error": "Forbidden: minimum role tier not met",
                    "minimum_required": min_role.value,
                }), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator