"""Deterministic shared date/datetime resolution utilities.

Used by agent validation/clarification before strict domain tools execute.
Compatibility target: Python 3.9+.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, time, timedelta
from typing import Any, Optional, Union


ReferenceValue = Union[str, date, datetime]


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _reference_datetime(value: ReferenceValue) -> datetime:
    """Return a trusted reference datetime.

    Callers should normally pass AgentState.current_datetime. A local-time
    fallback is retained only for defensive compatibility with older callers.
    """

    if isinstance(value, datetime):
        return value

    if isinstance(value, date):
        return datetime.combine(
            value,
            time.min,
        )

    raw = str(value or "").strip()

    if raw:
        normalized = raw
        if normalized.endswith("Z"):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        try:
            return datetime.fromisoformat(
                normalized
            )
        except ValueError:
            try:
                parsed_date = date.fromisoformat(
                    normalized[:10]
                )
                return datetime.combine(
                    parsed_date,
                    time.min,
                )
            except ValueError:
                pass

    return datetime.now().astimezone()


def _shift_calendar_months(
    value: date,
    months: int,
) -> date:
    absolute_month = (
        value.year * 12
        + (value.month - 1)
        + months
    )

    target_year, zero_based_month = divmod(
        absolute_month,
        12,
    )
    target_month = zero_based_month + 1

    target_day = min(
        value.day,
        calendar.monthrange(
            target_year,
            target_month,
        )[1],
    )

    return date(
        target_year,
        target_month,
        target_day,
    )


def _shift_calendar_years(
    value: date,
    years: int,
) -> date:
    target_year = value.year + years

    target_day = min(
        value.day,
        calendar.monthrange(
            target_year,
            value.month,
        )[1],
    )

    return date(
        target_year,
        value.month,
        target_day,
    )


def _weekday_date(
    reference: date,
    weekday: int,
    modifier: str,
) -> date:
    if modifier == "last":
        delta = (
            reference.weekday() - weekday
        ) % 7
        if delta == 0:
            delta = 7
        return reference - timedelta(
            days=delta
        )

    if modifier == "this":
        start_of_week = (
            reference
            - timedelta(
                days=reference.weekday()
            )
        )
        return start_of_week + timedelta(
            days=weekday
        )

    # Bare weekday and "next weekday" both mean the next occurrence.
    delta = (
        weekday - reference.weekday()
    ) % 7

    if modifier == "next" and delta == 0:
        delta = 7

    return reference + timedelta(
        days=delta
    )


def resolve_relative_date(
    value: Any,
    current_datetime: ReferenceValue,
) -> Optional[str]:
    """Resolve common date wording to YYYY-MM-DD.

    Deterministic semantics:
    - next/last week: +/- 7 days
    - next/last month: same calendar day in adjacent month, clamped
    - next/last year: same calendar date in adjacent year, clamped
    - next/last/this weekday and bare weekday
    - in N days/weeks/months/years
    - N days/weeks/months/years ago
    - ISO dates or datetimes
    """

    raw = " ".join(
        str(value or "").strip().split()
    )

    if not raw:
        return None

    lowered = raw.casefold()
    reference = _reference_datetime(
        current_datetime
    ).date()

    iso_match = re.search(
        r"\b(\d{4}-\d{2}-\d{2})\b",
        raw,
    )

    if iso_match:
        candidate = iso_match.group(1)

        try:
            return date.fromisoformat(
                candidate
            ).isoformat()
        except ValueError:
            return None

    if re.search(
        r"\byesterday\b",
        lowered,
    ):
        return (
            reference
            - timedelta(days=1)
        ).isoformat()

    if re.search(
        r"\btoday\b",
        lowered,
    ):
        return reference.isoformat()

    if re.search(
        r"\btomorrow\b",
        lowered,
    ):
        return (
            reference
            + timedelta(days=1)
        ).isoformat()

    if re.search(
        r"\bnext\s+week\b",
        lowered,
    ):
        return (
            reference
            + timedelta(days=7)
        ).isoformat()

    if re.search(
        r"\blast\s+week\b",
        lowered,
    ):
        return (
            reference
            - timedelta(days=7)
        ).isoformat()

    if re.search(
        r"\bnext\s+month\b",
        lowered,
    ):
        return _shift_calendar_months(
            reference,
            1,
        ).isoformat()

    if re.search(
        r"\blast\s+month\b",
        lowered,
    ):
        return _shift_calendar_months(
            reference,
            -1,
        ).isoformat()

    if re.search(
        r"\bnext\s+year\b",
        lowered,
    ):
        return _shift_calendar_years(
            reference,
            1,
        ).isoformat()

    if re.search(
        r"\blast\s+year\b",
        lowered,
    ):
        return _shift_calendar_years(
            reference,
            -1,
        ).isoformat()

    weekday_match = re.search(
        r"\b(?:(next|last|this)\s+)?"
        r"(monday|tuesday|wednesday|thursday|"
        r"friday|saturday|sunday)\b",
        lowered,
    )

    if weekday_match:
        modifier = (
            weekday_match.group(1)
            or ""
        )
        weekday = _WEEKDAYS[
            weekday_match.group(2)
        ]

        return _weekday_date(
            reference,
            weekday,
            modifier,
        ).isoformat()

    in_match = re.search(
        r"\bin\s+(\d+)\s+"
        r"(day|days|week|weeks|month|months|year|years)\b",
        lowered,
    )

    if in_match:
        amount = int(
            in_match.group(1)
        )
        unit = in_match.group(2)

        if unit.startswith("day"):
            result = (
                reference
                + timedelta(days=amount)
            )
        elif unit.startswith("week"):
            result = (
                reference
                + timedelta(weeks=amount)
            )
        elif unit.startswith("month"):
            result = _shift_calendar_months(
                reference,
                amount,
            )
        else:
            result = _shift_calendar_years(
                reference,
                amount,
            )

        return result.isoformat()

    ago_match = re.search(
        r"\b(\d+)\s+"
        r"(day|days|week|weeks|month|months|year|years)"
        r"\s+ago\b",
        lowered,
    )

    if ago_match:
        amount = int(
            ago_match.group(1)
        )
        unit = ago_match.group(2)

        if unit.startswith("day"):
            result = (
                reference
                - timedelta(days=amount)
            )
        elif unit.startswith("week"):
            result = (
                reference
                - timedelta(weeks=amount)
            )
        elif unit.startswith("month"):
            result = _shift_calendar_months(
                reference,
                -amount,
            )
        else:
            result = _shift_calendar_years(
                reference,
                -amount,
            )

        return result.isoformat()

    return None


def _extract_time(
    value: Any,
) -> Optional[time]:
    raw = " ".join(
        str(value or "").strip().split()
    )

    if not raw:
        return None

    lowered = raw.casefold()

    if re.search(
        r"\bnoon\b",
        lowered,
    ):
        return time(12, 0)

    if re.search(
        r"\bmidnight\b",
        lowered,
    ):
        return time(0, 0)

    twelve_hour = re.search(
        r"\b(\d{1,2})"
        r"(?::(\d{2}))?\s*"
        r"(am|pm)\b",
        lowered,
    )

    if twelve_hour:
        hour = int(
            twelve_hour.group(1)
        )
        minute = int(
            twelve_hour.group(2)
            or 0
        )

        if not (
            1 <= hour <= 12
            and 0 <= minute <= 59
        ):
            return None

        meridiem = twelve_hour.group(3)

        if hour == 12:
            hour = 0

        if meridiem == "pm":
            hour += 12

        return time(
            hour,
            minute,
        )

    twenty_four = re.search(
        r"(?<![T\d])"
        r"\b([01]?\d|2[0-3]):([0-5]\d)\b",
        lowered,
    )

    if twenty_four:
        return time(
            int(twenty_four.group(1)),
            int(twenty_four.group(2)),
        )

    # Named dayparts are intentionally deterministic defaults.
    named_times = (
        ("morning", time(9, 0)),
        ("afternoon", time(15, 0)),
        ("evening", time(19, 0)),
        ("night", time(21, 0)),
    )

    for token, resolved in named_times:
        if re.search(
            r"\b{}\b".format(
                re.escape(token)
            ),
            lowered,
        ):
            return resolved

    return None


def resolve_relative_datetime(
    value: Any,
    current_datetime: ReferenceValue,
    *,
    default_date: Any = None,
) -> Optional[str]:
    """Resolve relative date + explicit time to an ISO datetime.

    ``default_date`` allows a prior clarification turn to preserve the chosen
    date while the user supplies only a time, e.g.:
        date="next Monday", reply="6 PM"
    """

    raw = " ".join(
        str(value or "").strip().split()
    )

    if not raw:
        return None

    normalized = raw
    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )

        # A date-only ISO string is accepted by fromisoformat as midnight only
        # in some call patterns; require an explicit datetime separator here.
        if "T" in normalized or " " in normalized:
            return parsed.isoformat()
    except ValueError:
        pass

    resolved_date = resolve_relative_date(
        raw,
        current_datetime,
    )

    if (
        resolved_date is None
        and default_date is not None
    ):
        resolved_date = resolve_relative_date(
            default_date,
            current_datetime,
        )

    if resolved_date is None:
        return None

    resolved_time = _extract_time(
        raw
    )

    if resolved_time is None:
        return None

    reference = _reference_datetime(
        current_datetime
    )

    result = datetime.combine(
        date.fromisoformat(
            resolved_date
        ),
        resolved_time,
        tzinfo=reference.tzinfo,
    )

    return result.isoformat()
