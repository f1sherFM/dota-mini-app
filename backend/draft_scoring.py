"""Shared confidence-aware helpers for draft synergy and matchups.

STRATZ pair values are estimates: an extreme value based on a few hundred
matches is less reliable than a smaller value based on tens of thousands.
Synergy is therefore shrunk smoothly towards zero using a 1000-match prior.
Matchups intentionally remain unchanged until they are evaluated separately.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


SYNERGY_PRIOR_MATCHES = 1000


def _finite_float(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return parsed if math.isfinite(parsed) else 0.0


def _nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def confidence_weighted_synergy(
    record: Mapping[str, Any] | None,
    *,
    prior_matches: int = SYNERGY_PRIOR_MATCHES,
) -> float:
    """Return ``synergy * n / (n + prior)`` for one directional record.

    Missing, malformed and non-finite values are neutral. A non-positive prior
    is supported for diagnostics and returns the raw finite synergy value.
    """

    if not record:
        return 0.0

    synergy = _finite_float(record.get("synergy"))
    if prior_matches <= 0:
        return synergy

    match_count = _nonnegative_int(record.get("matchCount"))
    if match_count == 0:
        return 0.0
    return synergy * match_count / (match_count + prior_matches)


def _pair_record(
    matchups: Mapping[str, Any],
    map_key: str,
    first: int,
    second: int,
) -> Mapping[str, Any] | None:
    hero = matchups.get(str(first))
    if not isinstance(hero, Mapping):
        return None
    pair_map = hero.get(map_key)
    if not isinstance(pair_map, Mapping):
        return None
    record = pair_map.get(str(second))
    return record if isinstance(record, Mapping) else None


def symmetric_synergy(
    matchups: Mapping[str, Any],
    first: int,
    second: int,
) -> float:
    """Confidence-weighted average of both directional ``with`` records."""

    forward = confidence_weighted_synergy(
        _pair_record(matchups, "with", first, second)
    )
    reverse = confidence_weighted_synergy(
        _pair_record(matchups, "with", second, first)
    )
    return (forward + reverse) / 2


def antisymmetric_matchup(
    matchups: Mapping[str, Any],
    first: int,
    second: int,
) -> float:
    """Current raw matchup formula; deliberately unaffected by S1000."""

    forward = _finite_float(
        (_pair_record(matchups, "vs", first, second) or {}).get("synergy")
    )
    reverse = _finite_float(
        (_pair_record(matchups, "vs", second, first) or {}).get("synergy")
    )
    return (forward - reverse) / 2
