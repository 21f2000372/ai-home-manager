"""Password hashing helpers.

Prefers bcrypt (via passlib) when the dependency is installed. Falls back to a
standard-library PBKDF2-HMAC-SHA256 implementation so the database and seed
script work before ``pip install -r requirements.txt`` has been run.

Hash format for the fallback: ``pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>``
This is self-describing, so ``verify_password`` can detect which scheme a stored
hash uses. bcrypt hashes (``$2b$...``) are handled by passlib when present.
"""

from __future__ import annotations

import hashlib
import hmac
import os

_PBKDF2_ITERATIONS = 260_000
_PBKDF2_PREFIX = "pbkdf2_sha256"

try:  # Preferred: bcrypt via passlib
    from passlib.context import CryptContext

    _pwd_context: "CryptContext | None" = CryptContext(schemes=["bcrypt"], deprecated="auto")
except Exception:  # pragma: no cover - fallback path when passlib is absent
    _pwd_context = None


def hash_password(plain: str) -> str:
    """Hash a plaintext password for storage."""
    if _pwd_context is not None:
        return _pwd_context.hash(plain)

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"{_PBKDF2_PREFIX}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(plain: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored hash (either scheme)."""
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

    # bcrypt / other passlib-managed hash
    if _pwd_context is not None:
        try:
            return _pwd_context.verify(plain, stored_hash)
        except Exception:
            return False
    return False
