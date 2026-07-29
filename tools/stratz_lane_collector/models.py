"""Typed structures for aggregated lane-outcome data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias


@dataclass
class LaneStat:
    match_count: int = 0
    draw_count: int = 0
    win_count: int = 0
    loss_count: int = 0
    stomp_win_count: int = 0
    stomp_loss_count: int = 0
    match_win_count: int = 0
    cs_count: int = 0

    def add(self, other: "LaneStat") -> None:
        self.match_count += other.match_count
        self.draw_count += other.draw_count
        self.win_count += other.win_count
        self.loss_count += other.loss_count
        self.stomp_win_count += other.stomp_win_count
        self.stomp_loss_count += other.stomp_loss_count
        self.match_win_count += other.match_win_count
        self.cs_count += other.cs_count


HeroLanes: TypeAlias = dict[str, dict[str, LaneStat]]
LaneModeData: TypeAlias = dict[str, HeroLanes]
LaneData: TypeAlias = dict[str, LaneModeData]
