from __future__ import annotations

import math
import unittest
from pathlib import Path

from backend.draft_scoring import (
    SYNERGY_PRIOR_MATCHES,
    antisymmetric_matchup,
    confidence_weighted_synergy,
    symmetric_synergy,
)


class ConfidenceWeightedSynergyTests(unittest.TestCase):
    def test_prior_is_the_replayed_s1000_value(self):
        self.assertEqual(SYNERGY_PRIOR_MATCHES, 1000)

    def test_small_samples_are_shrunk_smoothly(self):
        self.assertAlmostEqual(
            confidence_weighted_synergy(
                {"synergy": 6.5, "matchCount": 250}
            ),
            1.3,
        )
        self.assertAlmostEqual(
            confidence_weighted_synergy(
                {"synergy": 2.28, "matchCount": 18_000}
            ),
            2.16,
        )

    def test_negative_values_are_also_shrunk_towards_zero(self):
        self.assertAlmostEqual(
            confidence_weighted_synergy(
                {"synergy": -5, "matchCount": 1000}
            ),
            -2.5,
        )

    def test_missing_or_malformed_records_are_neutral(self):
        self.assertEqual(confidence_weighted_synergy(None), 0)
        self.assertEqual(
            confidence_weighted_synergy(
                {"synergy": 10, "matchCount": 0}
            ),
            0,
        )
        self.assertEqual(
            confidence_weighted_synergy(
                {"synergy": "bad", "matchCount": "bad"}
            ),
            0,
        )
        self.assertEqual(
            confidence_weighted_synergy(
                {"synergy": math.inf, "matchCount": 1000}
            ),
            0,
        )

    def test_directional_records_are_weighted_before_averaging(self):
        matchups = {
            "1": {
                "with": {
                    "2": {"synergy": 6, "matchCount": 500}
                }
            },
            "2": {
                "with": {
                    "1": {"synergy": 2, "matchCount": 3000}
                }
            },
        }
        # 6 × 500/1500 = 2; 2 × 3000/4000 = 1.5; average = 1.75.
        self.assertAlmostEqual(symmetric_synergy(matchups, 1, 2), 1.75)
        self.assertAlmostEqual(symmetric_synergy(matchups, 2, 1), 1.75)


class MatchupTests(unittest.TestCase):
    def test_matchups_remain_raw_and_antisymmetric(self):
        matchups = {
            "1": {
                "vs": {
                    "2": {"synergy": 4, "matchCount": 10}
                }
            },
            "2": {
                "vs": {
                    "1": {"synergy": -2, "matchCount": 10}
                }
            },
        }
        self.assertEqual(antisymmetric_matchup(matchups, 1, 2), 3)
        self.assertEqual(antisymmetric_matchup(matchups, 2, 1), -3)


class ScoringContractTests(unittest.TestCase):
    def test_frontend_uses_the_same_prior_and_new_battles_are_v3(self):
        project_root = Path(__file__).resolve().parents[1]
        script = (project_root / "script.js").read_text(encoding="utf-8")
        api = (project_root / "backend" / "api.py").read_text(encoding="utf-8")

        self.assertIn(
            f"var _ANALYSIS_SYNERGY_PRIOR_MATCHES = {SYNERGY_PRIOR_MATCHES};",
            script,
        )
        self.assertIn(
            '"scoring": {"v": 3, "synergy_max":',
            api,
        )


if __name__ == "__main__":
    unittest.main()
