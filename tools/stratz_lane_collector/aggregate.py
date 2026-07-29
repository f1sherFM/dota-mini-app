"""Normalization and aggregation of STRATZ laneOutcome rows."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from tools.stratz_collector.aggregate import DataShapeError

from .models import LaneData, LaneModeData, LaneStat


LANES = frozenset({"SAFE", "MID", "OFF"})
COUNT_FIELDS = {
    "matchCount": "match_count",
    "drawCount": "draw_count",
    "winCount": "win_count",
    "lossCount": "loss_count",
    "stompWinCount": "stomp_win_count",
    "stompLossCount": "stomp_loss_count",
    "matchWinCount": "match_win_count",
    "csCount": "cs_count",
}


def _hero_id(value: Any, *, field: str) -> str:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DataShapeError(f"{field} must be an integer hero id") from exc
    if parsed <= 0:
        raise DataShapeError(f"{field} must be positive, got {parsed}")
    return str(parsed)


def _count(value: Any, *, field: str, pair: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise DataShapeError(f"{field} for {pair} must be an integer") from exc
    if parsed < 0:
        raise DataShapeError(f"{field} for {pair} must not be negative")
    return parsed


def _parse_stat(row: Mapping[str, Any], *, pair: str) -> LaneStat:
    values = {
        attr: _count(row.get(field), field=field, pair=pair)
        for field, attr in COUNT_FIELDS.items()
    }
    stat = LaneStat(**values)
    classified = (
        stat.draw_count + stat.win_count + stat.loss_count
        + stat.stomp_win_count + stat.stomp_loss_count
    )
    if classified > stat.match_count:
        raise DataShapeError(f"lane outcomes exceed matchCount for {pair}")
    if stat.match_win_count > stat.match_count:
        raise DataShapeError(f"matchWinCount exceeds matchCount for {pair}")
    return stat


def parse_rows(
    rows: Any,
    allowed_hero_ids: Iterable[str],
    *,
    description: str,
    lane: str,
) -> LaneModeData:
    """Parse and combine one STRATZ laneOutcome response.

    STRATZ may return separate rows for rank brackets. They intentionally merge
    into the same hero/lane/pair entry when no rank filter is configured.
    """
    if not isinstance(rows, list) or not rows:
        raise DataShapeError(f"STRATZ returned no lane outcomes for {description}")
    if lane not in LANES:
        raise DataShapeError(f"unexpected lane {lane!r} for {description}")
    allowed = set(allowed_hero_ids)
    result: LaneModeData = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise DataShapeError(f"lane outcome for {description} must be an object")
        raw_source_id = row.get("heroId1")
        raw_target_id = row.get("heroId2")
        try:
            if int(raw_source_id) <= 0 or int(raw_target_id) <= 0:
                # STRATZ occasionally includes aggregate service rows such as hero 0.
                continue
        except (TypeError, ValueError) as exc:
            raise DataShapeError("lane outcome contains a non-numeric hero id") from exc
        source_id = _hero_id(raw_source_id, field="heroId1")
        target_id = _hero_id(raw_target_id, field="heroId2")
        if source_id not in allowed or target_id not in allowed or source_id == target_id:
            continue
        pair = f"{source_id}->{target_id}, {lane}, {description}"
        stat = _parse_stat(row, pair=pair)
        target = (
            result.setdefault(source_id, {})
            .setdefault(lane, {})
            .setdefault(target_id, LaneStat())
        )
        target.add(stat)
    if not result:
        raise DataShapeError(f"STRATZ returned no playable lane outcomes for {description}")
    return result


def aggregate_snapshots(snapshots: Iterable[LaneData]) -> LaneData:
    """Sum counters across completed weeks, lane groups, and rank rows."""
    result: LaneData = {"with": {}, "against": {}}
    for snapshot in snapshots:
        for mode in ("with", "against"):
            for hero_id, lanes in snapshot.get(mode, {}).items():
                for lane, pairs in lanes.items():
                    for other_id, stat in pairs.items():
                        target = (
                            result[mode].setdefault(hero_id, {})
                            .setdefault(lane, {})
                            .setdefault(other_id, LaneStat())
                        )
                        target.add(stat)
    return result


def to_jsonable(data: LaneData) -> dict[str, dict]:
    def serialize_mode(mode: LaneModeData) -> dict[str, dict]:
        return {
            hero_id: {
                lane: {
                    other_id: {
                        "matchCount": stat.match_count,
                        "drawCount": stat.draw_count,
                        "winCount": stat.win_count,
                        "lossCount": stat.loss_count,
                        "stompWinCount": stat.stomp_win_count,
                        "stompLossCount": stat.stomp_loss_count,
                        "matchWinCount": stat.match_win_count,
                        "csCount": stat.cs_count,
                    }
                    for other_id, stat in sorted(pairs.items(), key=lambda item: int(item[0]))
                }
                for lane, pairs in sorted(lanes.items())
            }
            for hero_id, lanes in sorted(mode.items(), key=lambda item: int(item[0]))
        }

    return {mode: serialize_mode(data[mode]) for mode in ("with", "against")}
