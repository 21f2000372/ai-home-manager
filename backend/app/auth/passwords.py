"""Password hashing helpers using pure bcrypt with a PBKDF2 fallback."""
from __future__ import annotations

import hashlib
import hmac
import os

_PBKDF2_ITERATIONS = 260_000
_PBKDF2_PREFIX = "pbkdf2_sha256"

try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False


def hash_password(plain: str) -> str:
    """Hash a plaintext password for storage."""
    if _HAS_BCRYPT:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"{_PBKDF2_PREFIX}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored hash."""
    if stored_hash.startswith(_PBKDF2_PREFIX + "$"):
        try:
            _, iterations_s, salt_hex, hash_hex = stored_hash.split("$", 3)
            iterations = int(iterations_s)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(hash_hex)
        except (ValueError, TypeError):
            return False
        candidate = hashlib.pbkdf2_hmac(
            "sha256", plain.encode("utf-8"), salt, iterations
        )
        return hmac.compare_digest(candidate, expected)

    if _HAS_BCRYPT:
        try:
            return bcrypt.checkpw(
                plain.encode("utf-8"), stored_hash.encode("utf-8")
            )
        except Exception:
            return False

    return False