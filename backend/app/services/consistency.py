from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from decimal import Decimal
from difflib import SequenceMatcher
from app.db.base import SessionLocal
from app.models.inventory import GroceryItem, InventoryItem
from app.models.finance import Expense
from app.models.tasks import CalendarEvent, Task
from app.models.enums import TaskStatus
from datetime import datetime, timedelta, timezone
# ============================================================
# CANONICAL CONSISTENCY STATUSES
# ============================================================

CLEAR = "CLEAR"

EXACT_DUPLICATE = "EXACT_DUPLICATE"
POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"

QUANTITY_CONFLICT = "QUANTITY_CONFLICT"
TIME_CONFLICT = "TIME_CONFLICT"
STATE_CONFLICT = "STATE_CONFLICT"
OWNERSHIP_CONFLICT = "OWNERSHIP_CONFLICT"
RELATION_CONFLICT = "RELATION_CONFLICT"
VERSION_CONFLICT = "VERSION_CONFLICT"
CROSS_DOMAIN_CONFLICT = "CROSS_DOMAIN_CONFLICT"

BLOCKED = "BLOCKED"


CONSISTENCY_STATUSES = {
    CLEAR,
    EXACT_DUPLICATE,
    POSSIBLE_DUPLICATE,
    QUANTITY_CONFLICT,
    TIME_CONFLICT,
    STATE_CONFLICT,
    OWNERSHIP_CONFLICT,
    RELATION_CONFLICT,
    VERSION_CONFLICT,
    CROSS_DOMAIN_CONFLICT,
    BLOCKED,
}


# Higher value means the finding must take precedence when several
# consistency findings exist for the same proposed mutation.
_STATUS_PRIORITY = {
    CLEAR: 0,

    EXACT_DUPLICATE: 10,
    POSSIBLE_DUPLICATE: 20,

    QUANTITY_CONFLICT: 30,
    TIME_CONFLICT: 30,
    STATE_CONFLICT: 30,
    OWNERSHIP_CONFLICT: 30,
    RELATION_CONFLICT: 30,
    VERSION_CONFLICT: 30,
    CROSS_DOMAIN_CONFLICT: 30,

    BLOCKED: 40,
}


# ============================================================
# RESOLUTION TYPES
# ============================================================

SAME_OR_SEPARATE = "same_or_separate"
QUANTITY_RESOLUTION = "quantity_resolution"
TIME_RESOLUTION = "time_resolution"
STATE_RESOLUTION = "state_resolution"
OWNERSHIP_RESOLUTION = "ownership_resolution"
RELATION_RESOLUTION = "relation_resolution"
VERSION_RESOLUTION = "version_resolution"
CROSS_DOMAIN_RESOLUTION = "cross_domain_resolution"
BLOCKED_RESOLUTION = "blocked_resolution"


# ============================================================
# CANONICAL USER RESOLUTIONS
# ============================================================

USE_EXISTING = "use_existing"
CREATE_SEPARATE = "create_separate"

ADD_TO_EXISTING = "add_to_existing"
SET_EXISTING = "set_existing"
KEEP_EXISTING = "keep_existing"

UPDATE_EXISTING = "update_existing"
REPLACE_EXISTING = "replace_existing"

CHOOSE_NEW_TIME = "choose_new_time"
KEEP_PROPOSED_TIME = "keep_proposed_time"

LINK_EXISTING = "link_existing"
KEEP_BOTH = "keep_both"

REVISE_PROPOSED = "revise_proposed"
CANCEL_PROPOSED = "cancel_proposed"


# ============================================================
# FINDING
# ============================================================

@dataclass
class ConsistencyFinding:
    """
    One duplicate/conflict candidate discovered before mutation.

    This object is internal server state. ``candidate_id`` may contain
    a database identifier, but that identifier must never be exposed
    directly in user-facing clarification text.
    """

    code: str
    status: str

    domain: str
    operation: str

    details: str

    candidate_type: Optional[str] = None
    candidate_id: Optional[str] = None

    confidence: Optional[float] = None

    # Deterministic/semantic signals explaining why the candidate matched.
    #
    # Examples:
    # {
    #     "same_amount": True,
    #     "same_date": True,
    #     "description_similarity": 0.93,
    # }
    signals: Dict[str, Any] = field(
        default_factory=dict
    )

    # Tells the clarification/review layer what kind of question
    # needs to be asked.
    resolution_type: Optional[str] = None

    # Canonical choices the application can safely interpret.
    allowed_resolutions: List[str] = field(
        default_factory=list
    )

    # Additional server-only candidate information required for
    # later deterministic resolution.
    match: Dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if self.status not in CONSISTENCY_STATUSES:
            raise ValueError(
                "Unknown consistency status: {0}".format(
                    self.status
                )
            )

        if self.confidence is not None:
            self.confidence = max(
                0.0,
                min(1.0, float(self.confidence)),
            )

    @property
    def requires_resolution(self) -> bool:
        return self.status != CLEAR

    @property
    def priority(self) -> int:
        return _STATUS_PRIORITY.get(
            self.status,
            0,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "status": self.status,
            "domain": self.domain,
            "operation": self.operation,
            "details": self.details,
            "candidate_type": self.candidate_type,
            "candidate_id": self.candidate_id,
            "confidence": self.confidence,
            "signals": dict(self.signals),
            "resolution_type": self.resolution_type,
            "allowed_resolutions": list(
                self.allowed_resolutions
            ),
            "match": dict(self.match),
        }


# ============================================================
# RESULT
# ============================================================

@dataclass
class ConsistencyResult:
    """
    Result of checking one proposed mutation against household state.

    A proposed action can have multiple findings. For example, a new
    calendar event might be:

    - a possible duplicate of another event; AND
    - in a time conflict with a task.

    All findings are preserved. ``status`` represents the highest
    priority finding.
    """

    domain: str
    operation: str

    status: str = CLEAR

    findings: List[ConsistencyFinding] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:
        if self.status not in CONSISTENCY_STATUSES:
            raise ValueError(
                "Unknown consistency status: {0}".format(
                    self.status
                )
            )

    @property
    def clear(self) -> bool:
        return (
            self.status == CLEAR
            and not self.findings
        )

    @property
    def requires_resolution(self) -> bool:
        return any(
            finding.requires_resolution
            for finding in self.findings
        )

    @property
    def primary_finding(
        self,
    ) -> Optional[ConsistencyFinding]:
        if not self.findings:
            return None

        return max(
            self.findings,
            key=lambda finding: finding.priority,
        )

    def add(
        self,
        finding: ConsistencyFinding,
    ) -> None:
        self.findings.append(finding)
        self._refresh_status()

    def extend(
        self,
        findings: List[ConsistencyFinding],
    ) -> None:
        self.findings.extend(findings)
        self._refresh_status()

    def _refresh_status(self) -> None:
        if not self.findings:
            self.status = CLEAR
            return

        primary = self.primary_finding

        self.status = (
            primary.status
            if primary is not None
            else CLEAR
        )

    def to_dict(self) -> Dict[str, Any]:
        primary = self.primary_finding

        return {
            "domain": self.domain,
            "operation": self.operation,
            "status": self.status,
            "requires_resolution": (
                self.requires_resolution
            ),
            "primary_finding": (
                primary.to_dict()
                if primary is not None
                else None
            ),
            "findings": [
                finding.to_dict()
                for finding in self.findings
            ],
        }


# ============================================================
# SMALL CONSTRUCTORS
# ============================================================

def clear_result(
    domain: str,
    operation: str,
) -> ConsistencyResult:
    return ConsistencyResult(
        domain=domain,
        operation=operation,
        status=CLEAR,
    )


def result_from_findings(
    domain: str,
    operation: str,
    findings: List[ConsistencyFinding],
) -> ConsistencyResult:
    result = ConsistencyResult(
        domain=domain,
        operation=operation,
    )

    result.extend(findings)

    return result

# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def _normalize_text(
    value: Optional[str],
) -> str:
    return " ".join(
        str(value or "")
        .casefold()
        .strip()
        .split()
    )


def _number(
    value: Any,
) -> Optional[Decimal]:
    if value is None:
        return None

    try:
        return Decimal(str(value))
    except Exception:
        return None


def _quantity_text(
    quantity: Any,
    unit: Any,
) -> str:
    quantity_value = (
        str(quantity)
        if quantity is not None
        else "unspecified quantity"
    )

    normalized_unit = str(
        unit or ""
    ).strip()

    if normalized_unit:
        return "{0} {1}".format(
            quantity_value,
            normalized_unit,
        )

    return quantity_value

def _normalize_category(
    value: Any,
) -> str:
    normalized = _normalize_text(value)

    aliases = {
        "groceries": "grocery",
        "grocery items": "grocery",
    }

    return aliases.get(
        normalized,
        normalized,
    )


def _date_key(
    value: Any,
) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        return value.date().isoformat()

    raw = str(value).strip()

    if len(raw) >= 10:
        return raw[:10]

    return raw


def _timestamp_key(
    value: Any,
) -> str:
    if value is None:
        return ""

    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()

        if not raw:
            return ""

        try:
            parsed = datetime.fromisoformat(
                raw.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return raw

    if parsed.tzinfo is not None:
        parsed = (
            parsed
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

    return (
        parsed
        .replace(microsecond=0)
        .isoformat()
    )


def _datetime_value(
    value: Any,
) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()

        if not raw:
            return None

        try:
            parsed = datetime.fromisoformat(
                raw.replace(
                    "Z",
                    "+00:00",
                )
            )
        except ValueError:
            return None

    if parsed.tzinfo is not None:
        parsed = (
            parsed
            .astimezone(timezone.utc)
            .replace(tzinfo=None)
        )

    return parsed.replace(microsecond=0)


def _event_involves_user(
    event: Any,
    user_id: str,
) -> bool:
    if not user_id or len(user_id) != 36:
        return True

    if str(
        getattr(event, "owner_id", None)
        or ""
    ).strip() == user_id:
        return True

    attendees = (
        getattr(event, "attendees", None)
        or []
    )

    return any(
        str(
            getattr(attendee, "user_id", "")
            or ""
        ).strip() == user_id
        for attendee in attendees
    )


def _text_similarity(
    left: Any,
    right: Any,
) -> float:
    left_text = _normalize_text(left)
    right_text = _normalize_text(right)

    if not left_text or not right_text:
        return 0.0

    if left_text == right_text:
        return 1.0

    sequence_score = SequenceMatcher(
        None,
        left_text,
        right_text,
    ).ratio()

    left_tokens = set(
        left_text.split()
    )
    right_tokens = set(
        right_text.split()
    )

    union = left_tokens | right_tokens

    if not union:
        token_score = 0.0
    else:
        token_score = (
            len(left_tokens & right_tokens)
            / len(union)
        )

    return max(
        sequence_score,
        token_score,
    )


def _money_text(
    amount_minor: int,
    currency: str,
) -> str:
    return "{0:.2f} {1}".format(
        amount_minor / 100.0,
        currency,
    )
# ============================================================
# FOOD CONSISTENCY
# ============================================================

def _check_grocery_item(
    arguments: Dict[str, Any],
) -> ConsistencyResult:
    operation = "add_grocery_item"

    result = clear_result(
        "food",
        operation,
    )

    requested_name = _normalize_text(
        arguments.get("name")
    )

    if not requested_name:
        return result

    requested_quantity = _number(
        arguments.get("quantity")
    )

    requested_unit = _normalize_text(
        arguments.get("unit")
    )

    session = SessionLocal()

    try:
        rows = (
            session.query(GroceryItem)
            .filter(
                GroceryItem.purchased.is_(False)
            )
            .all()
        )

        for existing in rows:
            existing_name = _normalize_text(
                existing.name
            )

            if existing_name != requested_name:
                continue

            existing_quantity = _number(
                existing.quantity
            )

            existing_unit = _normalize_text(
                existing.unit
            )

            match = {
                "domain": "food",
                "record_type": "grocery_item",
                "record_id": str(
                    existing.grocery_item_id
                ),
                "record_id_arg": "grocery_item_id",
                "update_tool": "update_grocery_item",
                "name": existing.name,
                "quantity": (
                    float(existing.quantity)
                    if existing.quantity is not None
                    else None
                ),
                "unit": existing.unit,
            }

            # ------------------------------------------------
            # Same item but proposed quantity is incomplete.
            #
            # Normally clarification.py should have collected
            # quantity before this point, but fail safely if it
            # has not.
            # ------------------------------------------------
            if requested_quantity is None:
                result.add(
                    ConsistencyFinding(
                        code=(
                            "grocery_possible_duplicate"
                        ),
                        status=POSSIBLE_DUPLICATE,
                        domain="food",
                        operation=operation,
                        details=(
                            "'{0}' is already on the active "
                            "grocery list with quantity {1}."
                        ).format(
                            existing.name,
                            _quantity_text(
                                existing.quantity,
                                existing.unit,
                            ),
                        ),
                        candidate_type="grocery_item",
                        candidate_id=str(
                            existing.grocery_item_id
                        ),
                        confidence=0.85,
                        signals={
                            "same_normalized_name": True,
                            "requested_quantity_known": False,
                            "active_item": True,
                        },
                        resolution_type=(
                            QUANTITY_RESOLUTION
                        ),
                        allowed_resolutions=[
                            ADD_TO_EXISTING,
                            SET_EXISTING,
                            KEEP_EXISTING,
                            CREATE_SEPARATE,
                        ],
                        match=match,
                    )
                )

                continue

            exact_quantity = (
                requested_quantity
                == existing_quantity
            )

            exact_unit = (
                requested_unit
                == existing_unit
            )

            if exact_quantity and exact_unit:
                result.add(
                    ConsistencyFinding(
                        code="grocery_exact_duplicate",
                        status=EXACT_DUPLICATE,
                        domain="food",
                        operation=operation,
                        details=(
                            "'{0}' is already on the active "
                            "grocery list with quantity {1}."
                        ).format(
                            existing.name,
                            _quantity_text(
                                existing.quantity,
                                existing.unit,
                            ),
                        ),
                        candidate_type="grocery_item",
                        candidate_id=str(
                            existing.grocery_item_id
                        ),
                        confidence=1.0,
                        signals={
                            "same_normalized_name": True,
                            "same_quantity": True,
                            "same_unit": True,
                            "active_item": True,
                        },
                        resolution_type=(
                            QUANTITY_RESOLUTION
                        ),
                        allowed_resolutions=[
                            ADD_TO_EXISTING,
                            KEEP_EXISTING,
                            CREATE_SEPARATE,
                        ],
                        match=match,
                    )
                )

                continue

            result.add(
                ConsistencyFinding(
                    code="grocery_quantity_conflict",
                    status=QUANTITY_CONFLICT,
                    domain="food",
                    operation=operation,
                    details=(
                        "'{0}' is already on the active "
                        "grocery list as {1}, while the "
                        "new request is {2}."
                    ).format(
                        existing.name,
                        _quantity_text(
                            existing.quantity,
                            existing.unit,
                        ),
                        _quantity_text(
                            arguments.get("quantity"),
                            arguments.get("unit"),
                        ),
                    ),
                    candidate_type="grocery_item",
                    candidate_id=str(
                        existing.grocery_item_id
                    ),
                    confidence=1.0,
                    signals={
                        "same_normalized_name": True,
                        "same_quantity": exact_quantity,
                        "same_unit": exact_unit,
                        "active_item": True,
                    },
                    resolution_type=(
                        QUANTITY_RESOLUTION
                    ),
                    allowed_resolutions=[
                        ADD_TO_EXISTING,
                        SET_EXISTING,
                        KEEP_EXISTING,
                        CREATE_SEPARATE,
                    ],
                    match=match,
                )
            )

        return result

    finally:
        session.close()


def _check_inventory_item(
    arguments: Dict[str, Any],
) -> ConsistencyResult:
    operation = "add_inventory_item"

    result = clear_result(
        "food",
        operation,
    )

    requested_name = _normalize_text(
        arguments.get("name")
    )

    if not requested_name:
        return result

    requested_quantity = _number(
        arguments.get("quantity")
    )

    requested_unit = _normalize_text(
        arguments.get("unit")
    )

    session = SessionLocal()

    try:
        rows = session.query(
            InventoryItem
        ).all()

        for existing in rows:
            if (
                _normalize_text(existing.name)
                != requested_name
            ):
                continue

            existing_quantity = _number(
                existing.quantity
            )

            existing_unit = _normalize_text(
                existing.unit
            )

            match = {
                "domain": "food",
                "record_type": "inventory_item",
                "record_id": str(
                    existing.item_id
                ),
                "record_id_arg": "item_id",
                "update_tool": "update_inventory_item",
                "name": existing.name,
                "quantity": (
                    float(existing.quantity)
                    if existing.quantity is not None
                    else None
                ),
                "unit": existing.unit,
            }

            if requested_quantity is None:
                result.add(
                    ConsistencyFinding(
                        code=(
                            "inventory_possible_duplicate"
                        ),
                        status=POSSIBLE_DUPLICATE,
                        domain="food",
                        operation=operation,
                        details=(
                            "'{0}' already exists in "
                            "inventory with quantity {1}."
                        ).format(
                            existing.name,
                            _quantity_text(
                                existing.quantity,
                                existing.unit,
                            ),
                        ),
                        candidate_type="inventory_item",
                        candidate_id=str(
                            existing.item_id
                        ),
                        confidence=0.85,
                        signals={
                            "same_normalized_name": True,
                            "requested_quantity_known": False,
                        },
                        resolution_type=(
                            QUANTITY_RESOLUTION
                        ),
                        allowed_resolutions=[
                            ADD_TO_EXISTING,
                            SET_EXISTING,
                            KEEP_EXISTING,
                            CREATE_SEPARATE,
                        ],
                        match=match,
                    )
                )

                continue

            exact_quantity = (
                requested_quantity
                == existing_quantity
            )

            exact_unit = (
                requested_unit
                == existing_unit
            )

            if exact_quantity and exact_unit:
                result.add(
                    ConsistencyFinding(
                        code="inventory_exact_duplicate",
                        status=EXACT_DUPLICATE,
                        domain="food",
                        operation=operation,
                        details=(
                            "'{0}' already exists in "
                            "inventory with quantity {1}."
                        ).format(
                            existing.name,
                            _quantity_text(
                                existing.quantity,
                                existing.unit,
                            ),
                        ),
                        candidate_type="inventory_item",
                        candidate_id=str(
                            existing.item_id
                        ),
                        confidence=1.0,
                        signals={
                            "same_normalized_name": True,
                            "same_quantity": True,
                            "same_unit": True,
                        },
                        resolution_type=(
                            QUANTITY_RESOLUTION
                        ),
                        allowed_resolutions=[
                            ADD_TO_EXISTING,
                            KEEP_EXISTING,
                            CREATE_SEPARATE,
                        ],
                        match=match,
                    )
                )

                continue

            result.add(
                ConsistencyFinding(
                    code="inventory_quantity_conflict",
                    status=QUANTITY_CONFLICT,
                    domain="food",
                    operation=operation,
                    details=(
                        "'{0}' already exists in inventory "
                        "as {1}, while the new request "
                        "is {2}."
                    ).format(
                        existing.name,
                        _quantity_text(
                            existing.quantity,
                            existing.unit,
                        ),
                        _quantity_text(
                            arguments.get("quantity"),
                            arguments.get("unit"),
                        ),
                    ),
                    candidate_type="inventory_item",
                    candidate_id=str(
                        existing.item_id
                    ),
                    confidence=1.0,
                    signals={
                        "same_normalized_name": True,
                        "same_quantity": exact_quantity,
                        "same_unit": exact_unit,
                    },
                    resolution_type=(
                        QUANTITY_RESOLUTION
                    ),
                    allowed_resolutions=[
                        ADD_TO_EXISTING,
                        SET_EXISTING,
                        KEEP_EXISTING,
                        CREATE_SEPARATE,
                    ],
                    match=match,
                )
            )

        return result

    finally:
        session.close()

# ============================================================
# FINANCE CONSISTENCY
# ============================================================

def _check_expense(
    arguments: Dict[str, Any],
) -> ConsistencyResult:
    operation = "log_expense"

    result = clear_result(
        "finance",
        operation,
    )

    try:
        amount = int(
            arguments.get("amount_minor")
        )
    except (TypeError, ValueError):
        return result

    currency = str(
        arguments.get("currency")
        or ""
    ).upper().strip()

    occurred_at = arguments.get(
        "occurred_at"
    )

    requested_date = _date_key(
        occurred_at
    )

    if (
        amount <= 0
        or not currency
        or not requested_date
    ):
        return result

    requested_description = (
        _normalize_text(
            arguments.get("description")
        )
    )

    requested_category = (
        _normalize_category(
            arguments.get("category")
        )
    )

    requested_timestamp = (
        _timestamp_key(occurred_at)
    )

    requested_document_id = str(
        arguments.get("document_id")
        or ""
    ).strip()

    session = SessionLocal()

    try:
        # Household-wide by design.
        #
        # recorded_by is provenance only. It must NOT be used
        # to hide another household member's matching expense.
        rows = (
            session.query(Expense)
            .filter(
                Expense.amount_minor
                == amount
            )
            .all()
        )

        for existing in rows:
            existing_currency = str(
                existing.currency
                or ""
            ).upper().strip()

            if (
                existing_currency
                != currency
            ):
                continue

            existing_date = _date_key(
                existing.occurred_at
            )

            if existing_date != requested_date:
                continue

            existing_description = (
                _normalize_text(
                    existing.description
                )
            )

            existing_category = (
                _normalize_category(
                    existing.category
                )
            )

            description_similarity = (
                _text_similarity(
                    requested_description,
                    existing_description,
                )
            )

            same_description = bool(
                requested_description
                and existing_description
                and requested_description
                == existing_description
            )

            same_category = bool(
                requested_category
                and existing_category
                and requested_category
                == existing_category
            )

            same_timestamp = bool(
                requested_timestamp
                and requested_timestamp
                == _timestamp_key(
                    existing.occurred_at
                )
            )

            existing_document_id = str(
                getattr(
                    existing,
                    "document_id",
                    None,
                )
                or ""
            ).strip()

            same_document = bool(
                requested_document_id
                and existing_document_id
                and requested_document_id
                == existing_document_id
            )

            # ------------------------------------------------
            # Confidence score
            #
            # Same amount + currency + local date forms the
            # candidate window.
            # ------------------------------------------------

            confidence = 0.55

            if same_category:
                confidence += 0.10

            if description_similarity >= 0.90:
                confidence += 0.25
            elif description_similarity >= 0.70:
                confidence += 0.18
            elif description_similarity >= 0.50:
                confidence += 0.10

            if same_timestamp:
                confidence += 0.10

            if same_document:
                confidence += 0.35

            confidence = min(
                1.0,
                confidence,
            )

            # ------------------------------------------------
            # Exact identity requires stronger evidence than
            # merely same amount/date.
            # ------------------------------------------------

            exact_duplicate = (
                same_document
                or (
                    same_timestamp
                    and (
                        same_description
                        or same_category
                    )
                )
            )

            if exact_duplicate:
                status = EXACT_DUPLICATE
                code = (
                    "expense_exact_duplicate"
                )

            elif confidence >= 0.65:
                status = POSSIBLE_DUPLICATE
                code = (
                    "expense_possible_duplicate"
                )

            else:
                # Example:
                #
                # Rs 200 petrol
                # Rs 200 movie
                #
                # on the same day should not trigger merely
                # because amount/date happen to match.
                continue

            description_label = (
                existing.description
                or existing.category
                or "an expense"
            )

            details = (
                "A {0} expense for '{1}' is already "
                "logged on {2}."
            ).format(
                _money_text(
                    amount,
                    currency,
                ),
                description_label,
                existing_date,
            )

            match = {
                "domain": "finance",
                "record_type": "expense",
                "record_id": str(
                    existing.expense_id
                ),
                "record_id_arg": "expense_id",
                "update_tool": "update_expense",
                "amount_minor": (
                    existing.amount_minor
                ),
                "currency": (
                    existing.currency
                ),
                "category": (
                    existing.category
                ),
                "description": (
                    existing.description
                ),
                "occurred_at": str(
                    existing.occurred_at
                ),
            }

            result.add(
                ConsistencyFinding(
                    code=code,
                    status=status,
                    domain="finance",
                    operation=operation,
                    details=details,
                    candidate_type="expense",
                    candidate_id=str(
                        existing.expense_id
                    ),
                    confidence=confidence,
                    signals={
                        "same_amount": True,
                        "same_currency": True,
                        "same_local_date": True,
                        "same_category": (
                            same_category
                        ),
                        "same_description": (
                            same_description
                        ),
                        "description_similarity": (
                            round(
                                description_similarity,
                                4,
                            )
                        ),
                        "same_timestamp": (
                            same_timestamp
                        ),
                        "same_document": (
                            same_document
                        ),
                        "different_recorder": (
                            bool(
                                getattr(
                                    existing,
                                    "recorded_by",
                                    None,
                                )
                                and str(
                                    getattr(
                                        existing,
                                        "recorded_by",
                                        "",
                                    )
                                )
                                != str(
                                    arguments.get(
                                        "recorded_by"
                                    )
                                    or ""
                                )
                            )
                        ),
                    },
                    resolution_type=(
                        SAME_OR_SEPARATE
                    ),
                    allowed_resolutions=(
                        [
                            USE_EXISTING,
                            CREATE_SEPARATE,
                        ]
                        if status
                        == EXACT_DUPLICATE
                        else [
                            USE_EXISTING,
                            CREATE_SEPARATE,
                            REVISE_PROPOSED,
                        ]
                    ),
                    match=match,
                )
            )

        return result

    finally:
        session.close()
# ============================================================
# TASK CONSISTENCY
# ============================================================

def _check_task(
    arguments: Dict[str, Any],
) -> ConsistencyResult:
    operation = "create_task"

    result = clear_result(
        "tasks",
        operation,
    )

    requested_title = _normalize_text(
        arguments.get("title")
    )

    if not requested_title:
        return result

    requested_due = _timestamp_key(
        arguments.get("due_at")
    )

    requested_due_dt = _datetime_value(
        arguments.get("due_at")
    )

    requested_assignee = str(
        arguments.get("assigned_to")
        or ""
    ).strip()

    session = SessionLocal()

    try:
        # Household-wide by design. Only active tasks participate in
        # duplicate/conflict detection; completed/cancelled work is history.
        rows = (
            session.query(Task)
            .filter(
                Task.status.in_(
                    [
                        TaskStatus.OPEN,
                        TaskStatus.IN_PROGRESS,
                    ]
                )
            )
            .all()
        )

        for existing in rows:
            existing_title = _normalize_text(
                existing.title
            )

            title_similarity = _text_similarity(
                requested_title,
                existing_title,
            )

            exact_title = (
                requested_title
                == existing_title
            )

            similar_title = (
                not exact_title
                and title_similarity >= 0.82
            )

            if not exact_title and not similar_title:
                continue

            existing_due = _timestamp_key(
                existing.due_at
            )

            same_due = (
                requested_due
                == existing_due
            )

            requested_has_due = bool(
                requested_due
            )

            existing_has_due = bool(
                existing_due
            )

            one_due_missing = (
                requested_has_due
                != existing_has_due
            )

            existing_assignee = str(
                existing.assigned_to
                or ""
            ).strip()

            # The planner may supply a display name while the stored task
            # contains a user id. Only compare ownership when both values are
            # already the same stored id shape or when they are exactly equal.
            # Name -> id resolution remains the task tool's responsibility.
            same_assignee = (
                (
                    not requested_assignee
                    and not existing_assignee
                )
                or (
                    requested_assignee
                    and requested_assignee
                    == existing_assignee
                )
            )

            different_known_assignee = (
                bool(requested_assignee)
                and bool(existing_assignee)
                and len(requested_assignee) == 36
                and len(existing_assignee) == 36
                and requested_assignee != existing_assignee
            )

            match = {
                "domain": "tasks",
                "record_type": "task",
                "record_id": str(
                    existing.task_id
                ),
                "record_id_arg": "task_id",
                "update_tool": "update_task",
                "title": existing.title,
                "description": (
                    existing.description
                ),
                "due_at": (
                    str(existing.due_at)
                    if existing.due_at
                    is not None
                    else None
                ),
                "assigned_to": (
                    existing.assigned_to
                ),
                "status": (
                    existing.status.value
                    if hasattr(
                        existing.status,
                        "value",
                    )
                    else str(existing.status)
                ),
            }

            # ------------------------------------------------
            # Ownership conflict
            # ------------------------------------------------
            if (
                same_due
                and different_known_assignee
            ):
                result.add(
                    ConsistencyFinding(
                        code="task_ownership_conflict",
                        status=OWNERSHIP_CONFLICT,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "A matching active household task "
                            "named '{0}' already exists for the "
                            "same time but has a different "
                            "assignee."
                        ).format(
                            existing.title
                        ),
                        candidate_type="task",
                        candidate_id=str(
                            existing.task_id
                        ),
                        confidence=(
                            1.0
                            if exact_title
                            else min(
                                0.95,
                                max(
                                    0.82,
                                    title_similarity,
                                ),
                            )
                        ),
                        signals={
                            "same_normalized_title": (
                                exact_title
                            ),
                            "title_similarity": round(
                                title_similarity,
                                4,
                            ),
                            "same_due_time": True,
                            "different_assignee": True,
                            "active_task": True,
                        },
                        resolution_type=(
                            OWNERSHIP_RESOLUTION
                        ),
                        allowed_resolutions=[
                            KEEP_EXISTING,
                            UPDATE_EXISTING,
                            CREATE_SEPARATE,
                            REVISE_PROPOSED,
                            CANCEL_PROPOSED,
                        ],
                        match=match,
                    )
                )

                continue

            # ------------------------------------------------
            # Exact duplicate
            # ------------------------------------------------
            if (
                exact_title
                and same_due
                and (
                    same_assignee
                    or not requested_assignee
                    or not existing_assignee
                )
            ):
                result.add(
                    ConsistencyFinding(
                        code="task_exact_duplicate",
                        status=EXACT_DUPLICATE,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "An active household task "
                            "named '{0}' already exists"
                            "{1}."
                        ).format(
                            existing.title,
                            (
                                " with the same due time"
                                if existing_due
                                else ""
                            ),
                        ),
                        candidate_type="task",
                        candidate_id=str(
                            existing.task_id
                        ),
                        confidence=1.0,
                        signals={
                            "same_normalized_title": True,
                            "title_similarity": 1.0,
                            "same_due_time": True,
                            "same_assignee": (
                                same_assignee
                            ),
                            "active_task": True,
                        },
                        resolution_type=(
                            SAME_OR_SEPARATE
                        ),
                        allowed_resolutions=[
                            USE_EXISTING,
                            CREATE_SEPARATE,
                        ],
                        match=match,
                    )
                )

                continue

            # ------------------------------------------------
            # Same/similar task but a different known due time.
            # ------------------------------------------------
            if (
                requested_has_due
                and existing_has_due
                and not same_due
            ):
                result.add(
                    ConsistencyFinding(
                        code="task_time_conflict",
                        status=TIME_CONFLICT,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "A matching active household task "
                            "named '{0}' already exists with a "
                            "different due time."
                        ).format(
                            existing.title
                        ),
                        candidate_type="task",
                        candidate_id=str(
                            existing.task_id
                        ),
                        confidence=(
                            1.0
                            if exact_title
                            else min(
                                0.95,
                                max(
                                    0.82,
                                    title_similarity,
                                ),
                            )
                        ),
                        signals={
                            "same_normalized_title": (
                                exact_title
                            ),
                            "title_similarity": round(
                                title_similarity,
                                4,
                            ),
                            "same_due_time": False,
                            "existing_due_at": (
                                existing_due
                            ),
                            "requested_due_at": (
                                requested_due
                            ),
                            "active_task": True,
                        },
                        resolution_type=(
                            TIME_RESOLUTION
                        ),
                        allowed_resolutions=[
                            CHOOSE_NEW_TIME,
                            KEEP_PROPOSED_TIME,
                            UPDATE_EXISTING,
                            CREATE_SEPARATE,
                            CANCEL_PROPOSED,
                        ],
                        match=match,
                    )
                )

                continue

            # ------------------------------------------------
            # Similar identity but incomplete timing evidence.
            # ------------------------------------------------
            if (
                one_due_missing
                or similar_title
            ):
                result.add(
                    ConsistencyFinding(
                        code="task_possible_duplicate",
                        status=POSSIBLE_DUPLICATE,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "A similar active household task "
                            "named '{0}' already exists{1}."
                        ).format(
                            existing.title,
                            (
                                " at the same due time"
                                if same_due
                                and existing_due
                                else ""
                            ),
                        ),
                        candidate_type="task",
                        candidate_id=str(
                            existing.task_id
                        ),
                        confidence=(
                            0.85
                            if exact_title
                            else min(
                                0.95,
                                max(
                                    0.82,
                                    title_similarity,
                                ),
                            )
                        ),
                        signals={
                            "same_normalized_title": (
                                exact_title
                            ),
                            "title_similarity": round(
                                title_similarity,
                                4,
                            ),
                            "same_due_time": (
                                same_due
                            ),
                            "one_due_time_missing": (
                                one_due_missing
                            ),
                            "active_task": True,
                        },
                        resolution_type=(
                            SAME_OR_SEPARATE
                        ),
                        allowed_resolutions=[
                            USE_EXISTING,
                            CREATE_SEPARATE,
                            REVISE_PROPOSED,
                        ],
                        match=match,
                    )
                )

        # ----------------------------------------------------
        # Task -> Calendar time conflicts
        #
        # A scheduled task occupies the same 60-minute window
        # used by TaskService: [due_at - 60 min, due_at).
        # ----------------------------------------------------
        if requested_due_dt is not None:
            task_end = requested_due_dt
            task_start = (
                task_end
                - timedelta(minutes=60)
            )

            events = session.query(
                CalendarEvent
            ).all()

            for existing_event in events:
                if not _event_involves_user(
                    existing_event,
                    requested_assignee,
                ):
                    continue

                event_start = _datetime_value(
                    existing_event.starts_at
                )
                event_end = _datetime_value(
                    existing_event.ends_at
                )

                if (
                    event_start is None
                    or event_end is None
                ):
                    continue

                overlaps = (
                    event_start < task_end
                    and event_end > task_start
                )

                if not overlaps:
                    continue

                match = {
                    "domain": "tasks",
                    "record_type": "calendar_event",
                    "record_id": str(
                        existing_event.event_id
                    ),
                    "record_id_arg": "event_id",
                    "update_tool": (
                        "update_calendar_event"
                    ),
                    "title": existing_event.title,
                    "starts_at": str(
                        existing_event.starts_at
                    ),
                    "ends_at": str(
                        existing_event.ends_at
                    ),
                    "task_id": getattr(
                        existing_event,
                        "task_id",
                        None,
                    ),
                }

                result.add(
                    ConsistencyFinding(
                        code=(
                            "task_calendar_time_conflict"
                        ),
                        status=TIME_CONFLICT,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "The proposed task time overlaps "
                            "the household calendar event "
                            "'{0}'."
                        ).format(
                            existing_event.title
                        ),
                        candidate_type=(
                            "calendar_event"
                        ),
                        candidate_id=str(
                            existing_event.event_id
                        ),
                        confidence=1.0,
                        signals={
                            "strict_time_overlap": True,
                            "task_window_minutes": 60,
                            "calendar_event": True,
                        },
                        resolution_type=(
                            TIME_RESOLUTION
                        ),
                        allowed_resolutions=[
                            CHOOSE_NEW_TIME,
                            KEEP_PROPOSED_TIME,
                            UPDATE_EXISTING,
                            CANCEL_PROPOSED,
                        ],
                        match=match,
                    )
                )

        return result

    finally:
        session.close()

# ============================================================
# CALENDAR CONSISTENCY
# ============================================================

def _check_calendar_event(
    arguments: Dict[str, Any],
) -> ConsistencyResult:
    operation = "create_calendar_event"

    result = clear_result(
        "tasks",
        operation,
    )

    requested_title = _normalize_text(
        arguments.get("title")
    )

    requested_start = _datetime_value(
        arguments.get("starts_at")
    )

    requested_end = _datetime_value(
        arguments.get("ends_at")
    )

    if (
        not requested_title
        or requested_start is None
        or requested_end is None
        or requested_end <= requested_start
    ):
        return result

    requested_owner = str(
        arguments.get("owner_id")
        or ""
    ).strip()

    requested_task_id = str(
        arguments.get("task_id")
        or ""
    ).strip()

    session = SessionLocal()

    try:
        events = session.query(
            CalendarEvent
        ).all()

        for existing in events:
            if not _event_involves_user(
                existing,
                requested_owner,
            ):
                continue

            existing_start = _datetime_value(
                existing.starts_at
            )
            existing_end = _datetime_value(
                existing.ends_at
            )

            if (
                existing_start is None
                or existing_end is None
            ):
                continue

            existing_title = _normalize_text(
                existing.title
            )

            title_similarity = _text_similarity(
                requested_title,
                existing_title,
            )

            exact_title = (
                requested_title
                == existing_title
            )

            same_start = (
                requested_start
                == existing_start
            )

            same_end = (
                requested_end
                == existing_end
            )

            same_window = (
                same_start
                and same_end
            )

            start_delta_seconds = abs(
                (
                    requested_start
                    - existing_start
                ).total_seconds()
            )

            end_delta_seconds = abs(
                (
                    requested_end
                    - existing_end
                ).total_seconds()
            )

            near_window = (
                start_delta_seconds <= 900
                and end_delta_seconds <= 900
            )

            overlaps = (
                existing_start < requested_end
                and existing_end > requested_start
            )

            match = {
                "domain": "tasks",
                "record_type": "calendar_event",
                "record_id": str(
                    existing.event_id
                ),
                "record_id_arg": "event_id",
                "update_tool": (
                    "update_calendar_event"
                ),
                "title": existing.title,
                "starts_at": str(
                    existing.starts_at
                ),
                "ends_at": str(
                    existing.ends_at
                ),
                "owner_id": getattr(
                    existing,
                    "owner_id",
                    None,
                ),
                "task_id": getattr(
                    existing,
                    "task_id",
                    None,
                ),
            }

            if exact_title and same_window:
                result.add(
                    ConsistencyFinding(
                        code=(
                            "calendar_exact_duplicate"
                        ),
                        status=EXACT_DUPLICATE,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "A household calendar event "
                            "named '{0}' already exists "
                            "at the same time."
                        ).format(
                            existing.title
                        ),
                        candidate_type=(
                            "calendar_event"
                        ),
                        candidate_id=str(
                            existing.event_id
                        ),
                        confidence=1.0,
                        signals={
                            "same_normalized_title": True,
                            "same_start_time": True,
                            "same_end_time": True,
                        },
                        resolution_type=(
                            SAME_OR_SEPARATE
                        ),
                        allowed_resolutions=[
                            USE_EXISTING,
                            CREATE_SEPARATE,
                        ],
                        match=match,
                    )
                )
                continue

            plausible_same_event = (
                (
                    exact_title
                    or title_similarity >= 0.82
                )
                and near_window
            )

            if plausible_same_event:
                result.add(
                    ConsistencyFinding(
                        code=(
                            "calendar_possible_duplicate"
                        ),
                        status=POSSIBLE_DUPLICATE,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "A similar household calendar "
                            "event named '{0}' already exists "
                            "at nearly the same time."
                        ).format(
                            existing.title
                        ),
                        candidate_type=(
                            "calendar_event"
                        ),
                        candidate_id=str(
                            existing.event_id
                        ),
                        confidence=min(
                            0.95,
                            max(
                                0.82,
                                title_similarity,
                            ),
                        ),
                        signals={
                            "same_normalized_title": (
                                exact_title
                            ),
                            "title_similarity": round(
                                title_similarity,
                                4,
                            ),
                            "near_start_time": (
                                start_delta_seconds <= 900
                            ),
                            "near_end_time": (
                                end_delta_seconds <= 900
                            ),
                        },
                        resolution_type=(
                            SAME_OR_SEPARATE
                        ),
                        allowed_resolutions=[
                            USE_EXISTING,
                            CREATE_SEPARATE,
                            REVISE_PROPOSED,
                        ],
                        match=match,
                    )
                )
                continue

            if overlaps:
                result.add(
                    ConsistencyFinding(
                        code=(
                            "calendar_time_conflict"
                        ),
                        status=TIME_CONFLICT,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "The proposed calendar event "
                            "overlaps the household event "
                            "'{0}'."
                        ).format(
                            existing.title
                        ),
                        candidate_type=(
                            "calendar_event"
                        ),
                        candidate_id=str(
                            existing.event_id
                        ),
                        confidence=1.0,
                        signals={
                            "strict_time_overlap": True,
                            "same_normalized_title": (
                                exact_title
                            ),
                            "title_similarity": round(
                                title_similarity,
                                4,
                            ),
                        },
                        resolution_type=(
                            TIME_RESOLUTION
                        ),
                        allowed_resolutions=[
                            CHOOSE_NEW_TIME,
                            KEEP_PROPOSED_TIME,
                            UPDATE_EXISTING,
                            CREATE_SEPARATE,
                            CANCEL_PROPOSED,
                        ],
                        match=match,
                    )
                )

        # ----------------------------------------------------
        # Calendar -> Task time/relation conflicts
        # ----------------------------------------------------
        tasks = (
            session.query(Task)
            .filter(
                Task.status.in_(
                    [
                        TaskStatus.OPEN,
                        TaskStatus.IN_PROGRESS,
                    ]
                )
            )
            .all()
        )

        for existing_task in tasks:
            existing_assignee = str(
                existing_task.assigned_to
                or ""
            ).strip()

            if (
                requested_owner
                and len(requested_owner) == 36
                and existing_assignee
                and len(existing_assignee) == 36
                and requested_owner
                != existing_assignee
            ):
                continue

            task_due = _datetime_value(
                existing_task.due_at
            )

            if task_due is None:
                continue

            task_end = task_due
            task_start = (
                task_end
                - timedelta(minutes=60)
            )

            overlaps = (
                task_start < requested_end
                and task_end > requested_start
            )

            explicitly_linked = bool(
                requested_task_id
                and requested_task_id
                == str(existing_task.task_id)
            )

            match = {
                "domain": "tasks",
                "record_type": "task",
                "record_id": str(
                    existing_task.task_id
                ),
                "record_id_arg": "task_id",
                "update_tool": "update_task",
                "title": existing_task.title,
                "due_at": str(
                    existing_task.due_at
                ),
                "assigned_to": (
                    existing_task.assigned_to
                ),
                "status": (
                    existing_task.status.value
                    if hasattr(
                        existing_task.status,
                        "value",
                    )
                    else str(existing_task.status)
                ),
            }

            if explicitly_linked:
                if overlaps:
                    continue

                result.add(
                    ConsistencyFinding(
                        code=(
                            "calendar_task_relation_conflict"
                        ),
                        status=RELATION_CONFLICT,
                        domain="tasks",
                        operation=operation,
                        details=(
                            "The proposed calendar event is "
                            "linked to task '{0}', but its "
                            "time does not align with that "
                            "task's scheduled window."
                        ).format(
                            existing_task.title
                        ),
                        candidate_type="task",
                        candidate_id=str(
                            existing_task.task_id
                        ),
                        confidence=1.0,
                        signals={
                            "explicit_task_link": True,
                            "strict_time_overlap": False,
                            "task_window_minutes": 60,
                        },
                        resolution_type=(
                            RELATION_RESOLUTION
                        ),
                        allowed_resolutions=[
                            LINK_EXISTING,
                            CHOOSE_NEW_TIME,
                            REVISE_PROPOSED,
                            CANCEL_PROPOSED,
                        ],
                        match=match,
                    )
                )
                continue

            if not overlaps:
                continue

            result.add(
                ConsistencyFinding(
                    code=(
                        "calendar_task_time_conflict"
                    ),
                    status=TIME_CONFLICT,
                    domain="tasks",
                    operation=operation,
                    details=(
                        "The proposed calendar event "
                        "overlaps the scheduled household "
                        "task '{0}'."
                    ).format(
                        existing_task.title
                    ),
                    candidate_type="task",
                    candidate_id=str(
                        existing_task.task_id
                    ),
                    confidence=1.0,
                    signals={
                        "strict_time_overlap": True,
                        "task_window_minutes": 60,
                        "active_task": True,
                    },
                    resolution_type=(
                        TIME_RESOLUTION
                    ),
                    allowed_resolutions=[
                        CHOOSE_NEW_TIME,
                        KEEP_PROPOSED_TIME,
                        UPDATE_EXISTING,
                        CANCEL_PROPOSED,
                    ],
                    match=match,
                )
            )

        return result

    finally:
        session.close()

# ============================================================
# SHARED CONSISTENCY DISPATCHER
# ============================================================

_CONSISTENCY_CHECKERS = {
    "add_grocery_item": _check_grocery_item,
    "add_inventory_item": _check_inventory_item,
    "log_expense": _check_expense,
    "create_task": _check_task,
    "create_calendar_event": _check_calendar_event,
}


def check_consistency(
    domain: str,
    operation: str,
    arguments: Dict[str, Any],
    user_id: str = "",
) -> ConsistencyResult:
    """
    Run the shared household consistency check.

    ``user_id`` is accepted for provenance/future scoped policy, but
    duplicate detection is household-wide for the current single-household
    application. It must not filter otherwise-visible household records.
    """

    checker = _CONSISTENCY_CHECKERS.get(
        operation
    )

    if checker is None:
        return clear_result(
            domain,
            operation,
        )

    return checker(arguments)
