"""Completeness checks for aggregated STRATZ lane outcomes."""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from tools.stratz_collector.aggregate import DataShapeError

from .aggregate import LANES
from .models import LaneData


@dataclass(frozen=True)
class LaneValidationReport:
    hero_count: int
    pair_count: int
    total_matches: int
    low_sample_pairs: int


def validate_lane_data(
    data: LaneData,
    expected_hero_ids: set[str],
    *,
    low_sample_threshold: int = 500,
    expected_lanes: Collection[str] = LANES,
) -> LaneValidationReport:
    """Reject partial responses before an artifact is written."""
    total_pairs = 0
    total_matches = 0
    low_samples = 0
    heroes_seen: set[str] = set()
    for mode in ("with", "against"):
        actual = set(data.get(mode, {}))
        if actual != expected_hero_ids:
            missing = sorted(expected_hero_ids - actual, key=int)
            extra = sorted(actual - expected_hero_ids, key=int)
            raise DataShapeError(
                f"{mode} hero set differs from reference; missing={missing}, extra={extra}"
            )
        heroes_seen.update(actual)
        lanes_seen: set[str] = set()
        for lanes in data[mode].values():
            if not lanes:
                raise DataShapeError(f"{mode} contains a hero without lanes")
            lanes_seen.update(lanes)
            for pairs in lanes.values():
                for stat in pairs.values():
                    total_pairs += 1
                    total_matches += stat.match_count
                    if stat.match_count < low_sample_threshold:
                        low_samples += 1
        missing_lanes = set(expected_lanes) - lanes_seen
        if missing_lanes:
            raise DataShapeError(
                f"{mode} is missing requested lanes: {sorted(missing_lanes)}"
            )
    if not total_pairs or not total_matches:
        raise DataShapeError("lane outcome dataset is empty")
    return LaneValidationReport(
        hero_count=len(heroes_seen),
        pair_count=total_pairs,
        total_matches=total_matches,
        low_sample_pairs=low_samples,
    )
