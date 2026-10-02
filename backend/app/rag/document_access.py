"""Single source of truth for who may read a permanent document.

Documents are household-wide. Visibility is a minimum-role threshold:
Guest < Child < Adult < Admin.

A document's explicit ``min_role`` (when available) wins; otherwise the
classified domain's default minimum role applies.

Every document read path should use this policy so semantic retrieval,
SQL retrieval, direct lookup, and original-document access do not drift.

Compatible with Python 3.9.
"""

from __future__ import annotations

from typing import Any, Dict

from app.models.enums import HouseholdRole


DEFAULT_DOCUMENT_MIN_ROLE = HouseholdRole.ADULT


ROLE_RANK: Dict[HouseholdRole, int] = {
    HouseholdRole.GUEST: 0,
    HouseholdRole.CHILD: 1,
    HouseholdRole.ADULT: 2,
    HouseholdRole.ADMIN: 3,
}


DOMAIN_MIN_ROLE: Dict[str, HouseholdRole] = {
    "finance": HouseholdRole.ADULT,
    "food": HouseholdRole.CHILD,
    "maintenance": HouseholdRole.CHILD,
    "tasks": HouseholdRole.CHILD,
}


def _normalize_role(value: Any) -> HouseholdRole:
    """Convert a role value into HouseholdRole."""

    if isinstance(value, HouseholdRole):
        return value

    return HouseholdRole(str(value))


def resolve_min_role(document: Any) -> HouseholdRole:
    """Return the effective minimum role required to read a document.

    An explicit document-level min_role wins when present.

    Otherwise visibility is derived from the document's classified domain.

    Unknown or missing domains fail closed to Adult+.
    """

    explicit = getattr(document, "min_role", None)

    if explicit is not None:
        try:
            return _normalize_role(explicit)
        except (TypeError, ValueError):
            return DEFAULT_DOCUMENT_MIN_ROLE

    domain = str(
        getattr(document, "domain", "") or ""
    ).strip().casefold()

    return DOMAIN_MIN_ROLE.get(
        domain,
        DEFAULT_DOCUMENT_MIN_ROLE,
    )


def can_read_document(
    role: HouseholdRole,
    document: Any,
) -> bool:
    """Return True when the caller may read this document."""

    try:
        caller_role = _normalize_role(role)
    except (TypeError, ValueError):
        return False

    minimum_role = resolve_min_role(document)

    return (
        ROLE_RANK[caller_role]
        >= ROLE_RANK[minimum_role]
    )