from __future__ import annotations

import unittest

from tools.stratz_collector.aggregate import DataShapeError
from tools.stratz_lane_collector.aggregate import (
    aggregate_snapshots,
    parse_rows,
    to_jsonable,
)
from tools.stratz_lane_collector.validate import validate_lane_data


def _row(
    hero1: int,
    hero2: int,
    *,
    matches: int = 10,
    wins: int = 3,
    draws: int = 2,
    losses: int = 3,
    stomp_wins: int = 1,
    stomp_losses: int = 1,
) -> dict:
    return {
        "heroId1": hero1,
        "heroId2": hero2,
        "position": "POSITION_1",
        "matchCount": matches,
        "drawCount": draws,
        "winCount": wins,
        "lossCount": losses,
        "stompWinCount": stomp_wins,
        "stompLossCount": stomp_losses,
        "matchWinCount": 6,
        "csCount": 400,
    }


class ParseTests(unittest.TestCase):
    def test_rank_bracket_rows_are_combined(self):
        parsed = parse_rows(
            [_row(1, 2), _row(1, 2)],
            {"1", "2"},
            description="with, test",
        )
        stat = parsed["1"]["POSITION_1"]["2"]
        self.assertEqual(stat.match_count, 20)
        self.assertEqual(stat.win_count, 6)
        self.assertEqual(stat.cs_count, 800)

    def test_unknown_service_heroes_are_ignored(self):
        parsed = parse_rows(
            [_row(0, 2), _row(1, 2)],
            {"1", "2"},
            description="against, test",
        )
        self.assertEqual(set(parsed), {"1"})

    def test_malformed_hero_id_is_rejected(self):
        row = _row(1, 2)
        row["heroId1"] = "not-a-hero"
        with self.assertRaisesRegex(DataShapeError, "non-numeric"):
            parse_rows(
                [row],
                {"1", "2"},
                description="against, test",
            )

    def test_outcome_counts_cannot_exceed_matches(self):
        with self.assertRaisesRegex(DataShapeError, "outcomes exceed"):
            parse_rows(
                [_row(1, 2, matches=2)],
                {"1", "2"},
                description="against, test",
            )


class AggregationTests(unittest.TestCase):
    def test_completed_weeks_are_summed(self):
        first = parse_rows([_row(1, 2)], {"1", "2"}, description="first")
        second = parse_rows([_row(1, 2)], {"1", "2"}, description="second")
        result = aggregate_snapshots([
            {"with": first, "against": first},
            {"with": second, "against": second},
        ])
        encoded = to_jsonable(result)
        self.assertEqual(
            encoded["against"]["1"]["POSITION_1"]["2"]["matchCount"], 20,
        )


class ValidationTests(unittest.TestCase):
    def test_missing_hero_is_rejected(self):
        mode = parse_rows([_row(1, 2)], {"1", "2"}, description="test")
        with self.assertRaisesRegex(DataShapeError, "hero set differs"):
            validate_lane_data(
                {"with": mode, "against": mode},
                {"1", "2"},
            )

    def test_report_counts_pairs_and_low_samples(self):
        mode = parse_rows(
            [_row(1, 2), _row(2, 1)],
            {"1", "2"},
            description="test",
        )
        report = validate_lane_data(
            {"with": mode, "against": mode},
            {"1", "2"},
        )
        self.assertEqual(report.hero_count, 2)
        self.assertEqual(report.pair_count, 4)
        self.assertEqual(report.total_matches, 40)
        self.assertEqual(report.low_sample_pairs, 4)


if __name__ == "__main__":
    unittest.main()
