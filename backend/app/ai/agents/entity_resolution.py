from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
from typing import Callable, Iterable, TypeVar


T = TypeVar("T")


@dataclass(frozen=True)
class EntityMatch:
    entity: T
    entity_id: str
    label: str
    score: float
    matched_text: str


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize(value: str) -> str:
    return " ".join(_TOKEN_RE.findall((value or "").lower()))


def _tokens(value: str) -> set[str]:
    return set(_normalize(value).split())


def score_text_match(query: str, candidate_text: str) -> float:
    """Score a user query against searchable entity text.

    This intentionally uses only stdlib matching so every module can reuse it
    without adding a fuzzy-search dependency.
    """
    normalized_query = _normalize(query)
    normalized_candidate = _normalize(candidate_text)
    if not normalized_query or not normalized_candidate:
        return 0.0

    if normalized_query == normalized_candidate:
        return 1.0
    if normalized_query in normalized_candidate:
        return 0.92

    query_tokens = _tokens(normalized_query)
    candidate_tokens = _tokens(normalized_candidate)
    overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
    similarity = SequenceMatcher(None, normalized_query, normalized_candidate).ratio()
    return max(overlap * 0.85, similarity * 0.75)


def find_entity_matches(
    *,
    rows: Iterable[T],
    query: str,
    id_getter: Callable[[T], str],
    label_getter: Callable[[T], str],
    field_getters: list[Callable[[T], str | None]],
    limit: int = 5,
    min_score: float = 0.35,
) -> list[EntityMatch[T]]:
    matches: list[EntityMatch[T]] = []

    for row in rows:
        fields = [field(row) or "" for field in field_getters]
        searchable = " ".join(value for value in fields if value)
        score = score_text_match(query, searchable)
        if score < min_score:
            continue
        matches.append(EntityMatch(
            entity=row,
            entity_id=id_getter(row),
            label=label_getter(row),
            score=score,
            matched_text=searchable,
        ))

    matches.sort(key=lambda item: item.score, reverse=True)
    return matches[:limit]


def is_ambiguous_match(matches: list[EntityMatch[T]], *, margin: float = 0.12) -> bool:
    if len(matches) < 2:
        return False
    return matches[0].score - matches[1].score < margin

