"""JWT issuance, decoding, and validation utilities."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt

from app.config import config
from app.models.enums import HouseholdRole

JWT_ALGORITHM = "HS256"


def create_access_token(
    user_id: str,
    email: str,
    role: HouseholdRole,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Generate a signed JWT containing member identity and RBAC role."""
    now = datetime.now(timezone.utc)
    expire = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=config.JWT_EXPIRES_MINUTES)
    )

    payload: dict[str, Any] = {
        "sub": user_id,
        "email": email,
        "role": role.value,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT string.

    Raises jwt.PyJWTError on invalid signatures or expired tokens.
    """
    return jwt.decode(token, config.JWT_SECRET, algorithms=[JWT_ALGORITHM])