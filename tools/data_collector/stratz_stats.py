"""STRATZ hero-stat datasets used by D2Helper mini-games."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from math import isfinite
from pathlib import Path
from typing import Any

from tools.stratz_collector.__main__ import _atomic_json_write
from tools.stratz_collector.aggregate import DataShapeError
from tools.stratz_collector.client import StratzClient


DETAILED_STATS_QUERY = """
{
  heroStats {
    stats {
      heroId
      matchCount
      winCount
      kills
      deaths
      assists
      cs
      heroDamage
      towerDamage
      healingAllies
      stunDuration
      campsStacked
      kDAAverage
    }
  }
}
"""

CORE_FIELDS = ("heroId", "matchCount", "winCount")
DETAIL_FIELDS = (
    "heroId", "matchCount", "winCount", "kills", "deaths", "assists", "cs",
    "heroDamage", "towerDamage", "healingAllies", "stunDuration", "campsStacked",
    "kDAAverage",
)


def _non_negative_int(value: Any, *, field: str, hero_id: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DataShapeError(f"{field} for hero {hero_id} must be an integer") from exc
    if parsed < 0:
        raise DataShapeError(f"{field} for hero {hero_id} must not be negative")
    return parsed


def normalize_stats(
    rows: Any, *, expected_hero_ids: Collection[str] | None = None
) -> tuple[list[dict[str, int]], list[dict[str, Any]]]:
    """Validate STRATZ response and derive compact plus detailed datasets."""
    if not isinstance(rows, list) or not rows:
        raise DataShapeError("STRATZ returned no hero statistics")

    popularity: list[dict[str, int]] = []
    detailed: list[dict[str, Any]] = []
    seen: set[int] = set()
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise DataShapeError("STRATZ hero statistic must be an object")
        hero_id = _non_negative_int(raw.get("heroId"), field="heroId", hero_id=0)
        if hero_id <= 0:
            # Consistent with the matchup collector: service rows are not heroes.
            continue
        if hero_id in seen:
            raise DataShapeError(f"duplicate STRATZ statistic for hero {hero_id}")
        match_count = _non_negative_int(raw.get("matchCount"), field="matchCount", hero_id=hero_id)
        win_count = _non_negative_int(raw.get("winCount"), field="winCount", hero_id=hero_id)
        if win_count > match_count:
            raise DataShapeError(f"winCount for hero {hero_id} exceeds matchCount")
        seen.add(hero_id)
        popularity.append({
            "heroId": hero_id,
            "matchCount": match_count,
            "winCount": win_count,
        })
        row: dict[str, Any] = {
            "heroId": hero_id,
            "matchCount": match_count,
            "winCount": win_count,
        }
        for field in DETAIL_FIELDS[3:]:
            value = raw.get(field)
            if value is None:
                row[field] = None
                continue
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise DataShapeError(f"{field} for hero {hero_id} must be numeric") from exc
            if not isfinite(number):
                raise DataShapeError(f"{field} for hero {hero_id} must be finite")
            row[field] = value
        detailed.append(row)
    if not popularity:
        raise DataShapeError("STRATZ returned no playable heroes")
    if expected_hero_ids is not None:
        expected = {int(hero_id) for hero_id in expected_hero_ids}
        if seen != expected:
            missing = sorted(expected - seen)
            extra = sorted(seen - expected)
            raise DataShapeError(
                "STRATZ hero statistic set differs from reference; "
                f"missing={missing}, extra={extra}"
            )
    popularity.sort(key=lambda row: row["heroId"])
    detailed.sort(key=lambda row: row["heroId"])
    return popularity, detailed


async def collect_hero_stats(
    *,
    token: str,
    popularity_output: Path,
    detailed_output: Path,
    endpoint: str = "https://api.stratz.com/graphql",
    attempts: int = 5,
    expected_hero_ids: Collection[str] | None = None,
) -> dict[str, int]:
    """Fetch STRATZ once and write both mini-game data files atomically."""
    client = StratzClient(token.strip(), endpoint=endpoint, attempts=attempts)
    response = await client.execute({"query": DETAILED_STATS_QUERY, "variables": {}})
    try:
        rows = response["data"]["heroStats"]["stats"]
    except (KeyError, TypeError) as exc:
        raise DataShapeError("STRATZ hero statistics response has an unexpected shape") from exc
    popularity, detailed = normalize_stats(rows, expected_hero_ids=expected_hero_ids)
    _atomic_json_write(popularity_output, popularity)
    _atomic_json_write(detailed_output, detailed)
    return {
        "heroes": len(popularity),
        "total_matches": sum(row["matchCount"] for row in popularity),
    }
