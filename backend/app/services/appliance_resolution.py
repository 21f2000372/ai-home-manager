from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
import re
from typing import Any, List, Optional, Sequence, Tuple

from app.models.maintenance import Appliance


NO_MATCH = "NO_MATCH"
SINGLE_MATCH = "SINGLE_MATCH"
MULTIPLE_MATCHES = "MULTIPLE_MATCHES"
CONFIRMED = "CONFIRMED"


_ALIAS_GROUPS = (
    ("ac", "air conditioner", "air conditioning"),
    ("fridge", "refrigerator"),
    ("geyser", "water heater"),
    ("washer", "washing machine"),
    ("microwave", "microwave oven"),
    ("tv", "television"),
)


@dataclass(frozen=True)
class ApplianceCandidate:
    """One server-derived appliance candidate.

    appliance_id is intentionally internal. Use display_label for user-facing
    clarification text.
    """

    appliance_id: str
    display_label: str
    score: float
    name: str
    brand: Optional[str] = None
    model: Optional[str] = None


@dataclass
class ApplianceResolution:
    status: str
    reference: str
    candidates: List[ApplianceCandidate] = field(default_factory=list)
    confirmed_appliance_id: Optional[str] = None
    reason: str = ""


def _normalize(value: Any) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _alias_tokens(value: str) -> str:
    """Add deterministic aliases without replacing the original wording."""

    normalized = _normalize(value)
    if not normalized:
        return ""

    terms = {normalized}
    tokens = set(normalized.split())

    for group in _ALIAS_GROUPS:
        normalized_group = tuple(_normalize(item) for item in group)
        matched = any(
            alias == normalized
            or alias in tokens
            or (
                " " in alias
                and alias in normalized
            )
            for alias in normalized_group
        )
        if matched:
            terms.update(normalized_group)

    return " ".join(sorted(terms))


def _tokens(value: str) -> set:
    return set(_normalize(value).split())


def _token_score(reference: str, candidate: str) -> float:
    ref_tokens = _tokens(reference)
    candidate_tokens = _tokens(candidate)

    if not ref_tokens or not candidate_tokens:
        return 0.0

    intersection = ref_tokens & candidate_tokens
    if not intersection:
        return 0.0

    # Reference containment is important for generic queries such as "AC":
    # all plausible AC records should be surfaced rather than auto-selected.
    if ref_tokens <= candidate_tokens:
        return 0.90

    return len(intersection) / float(len(ref_tokens | candidate_tokens))


def _text_score(reference: str, candidate: str) -> float:
    if not reference or not candidate:
        return 0.0

    if reference == candidate:
        return 1.0

    sequence = SequenceMatcher(
        None,
        reference,
        candidate,
    ).ratio()

    token = _token_score(
        reference,
        candidate,
    )

    return max(sequence, token)


def _display_label(appliance: Appliance) -> str:
    name = str(getattr(appliance, "name", "") or "").strip()
    brand = str(getattr(appliance, "brand", "") or "").strip()
    model = str(getattr(appliance, "model", "") or "").strip()

    parts = []
    if name:
        parts.append(name)
    if brand and _normalize(brand) not in _tokens(name):
        parts.append(brand)
    if model:
        parts.append(model)

    if not parts:
        return "Unnamed appliance"

    return " — ".join(parts)


def _candidate_texts(appliance: Appliance) -> Tuple[str, ...]:
    name = _normalize(getattr(appliance, "name", ""))
    brand = _normalize(getattr(appliance, "brand", ""))
    model = _normalize(getattr(appliance, "model", ""))

    raw_values = [
        name,
        brand,
        model,
        " ".join(part for part in (brand, name) if part),
        " ".join(part for part in (name, model) if part),
        " ".join(part for part in (brand, model) if part),
        " ".join(part for part in (brand, name, model) if part),
    ]

    values = []
    seen = set()

    for value in raw_values:
        expanded = _alias_tokens(value)
        if expanded and expanded not in seen:
            seen.add(expanded)
            values.append(expanded)

    return tuple(values)


def _score_appliance(
    reference: str,
    appliance: Appliance,
) -> float:
    normalized_reference = _alias_tokens(reference)
    if not normalized_reference:
        return 0.0

    scores = [
        _text_score(
            normalized_reference,
            candidate_text,
        )
        for candidate_text in _candidate_texts(appliance)
    ]

    if not scores:
        return 0.0

    return max(scores)


def _all_appliances(session) -> Sequence[Appliance]:
    return session.query(Appliance).all()


def _find_by_id(
    session,
    appliance_id: str,
) -> Optional[Appliance]:
    getter = getattr(session, "get", None)
    if callable(getter):
        row = getter(Appliance, appliance_id)
        if row is not None:
            return row

    for row in _all_appliances(session):
        if str(getattr(row, "appliance_id", "")) == appliance_id:
            return row

    return None


def _to_candidate(
    appliance: Appliance,
    score: float,
) -> ApplianceCandidate:
    return ApplianceCandidate(
        appliance_id=str(
            getattr(appliance, "appliance_id", "")
        ),
        display_label=_display_label(appliance),
        score=round(float(score), 4),
        name=str(
            getattr(appliance, "name", "")
            or ""
        ).strip(),
        brand=(
            str(getattr(appliance, "brand", "") or "").strip()
            or None
        ),
        model=(
            str(getattr(appliance, "model", "") or "").strip()
            or None
        ),
    )


def resolve_appliance_reference(
    session,
    reference: Any,
    *,
    confirmed_appliance_id: Optional[str] = None,
    minimum_score: float = 0.56,
    max_candidates: int = 5,
) -> ApplianceResolution:
    """Resolve a human appliance reference without guessing.

    Rules:
    - A previously server-confirmed appliance id returns CONFIRMED.
    - No plausible records returns NO_MATCH.
    - One plausible record returns SINGLE_MATCH, never CONFIRMED.
    - Multiple plausible records returns MULTIPLE_MATCHES.
    - Candidate ranking is for display only; callers must obtain explicit user
      confirmation/selection before using an appliance id.
    """

    raw_reference = str(reference or "").strip()

    if confirmed_appliance_id:
        confirmed_id = str(
            confirmed_appliance_id
        ).strip()

        row = _find_by_id(
            session,
            confirmed_id,
        )

        if row is not None:
            return ApplianceResolution(
                status=CONFIRMED,
                reference=raw_reference,
                candidates=[
                    _to_candidate(
                        row,
                        1.0,
                    )
                ],
                confirmed_appliance_id=confirmed_id,
                reason=(
                    "The appliance was already confirmed "
                    "server-side for this workflow."
                ),
            )

        return ApplianceResolution(
            status=NO_MATCH,
            reference=raw_reference,
            reason=(
                "The previously confirmed appliance record "
                "no longer exists."
            ),
        )

    normalized_reference = _normalize(
        raw_reference
    )

    if not normalized_reference:
        return ApplianceResolution(
            status=NO_MATCH,
            reference=raw_reference,
            reason=(
                "No appliance reference was supplied."
            ),
        )

    ranked = []

    for appliance in _all_appliances(session):
        score = _score_appliance(
            normalized_reference,
            appliance,
        )

        if score < minimum_score:
            continue

        candidate = _to_candidate(
            appliance,
            score,
        )

        if not candidate.appliance_id:
            continue

        ranked.append(candidate)

    ranked.sort(
        key=lambda candidate: (
            -candidate.score,
            candidate.display_label.casefold(),
            candidate.appliance_id,
        )
    )

    # A detailed reference should not keep loosely related siblings merely
    # because they share a generic brand/type. Keep close alternatives for
    # genuinely ambiguous references, but narrow a clearly stronger match.
    if ranked:
        top_score = ranked[0].score
        if top_score >= 0.85:
            ranked = [
                candidate
                for candidate in ranked
                if (
                    candidate.score >= 0.90
                    or top_score - candidate.score <= 0.08
                )
            ]

    if max_candidates > 0:
        ranked = ranked[:max_candidates]

    if not ranked:
        return ApplianceResolution(
            status=NO_MATCH,
            reference=raw_reference,
            reason=(
                "No existing appliance record plausibly "
                "matches the reference."
            ),
        )

    if len(ranked) == 1:
        return ApplianceResolution(
            status=SINGLE_MATCH,
            reference=raw_reference,
            candidates=ranked,
            reason=(
                "One plausible appliance exists, but it "
                "still requires explicit user confirmation."
            ),
        )

    return ApplianceResolution(
        status=MULTIPLE_MATCHES,
        reference=raw_reference,
        candidates=ranked,
        reason=(
            "Several plausible appliances exist and the "
            "user must select one or choose to add a new appliance."
        ),
    )
