"""Auth package: password hashing and (later) JWT helpers."""
"""Auth package: password hashing, JWT operations, and RBAC decorators."""
from app.auth.passwords import hash_password, verify_password
from app.auth.jwt import create_access_token, decode_access_token
from app.auth.decorators import login_required, require_role, require_min_role

__all__ = [
    "hash_password",
    "verify_password",
    "create_access_token",
    "decode_access_token",
    "login_required",
    "require_role",
    "require_min_role",
]