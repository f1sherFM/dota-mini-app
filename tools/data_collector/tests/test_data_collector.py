from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.data_collector.d2pt import HERO_IDS, import_d2pt_builds, validate_builds
from tools.data_collector.stratz_stats import normalize_stats
from tools.stratz_collector.aggregate import DataShapeError


def _build() -> dict:
    return {
        "num_matches": 10,
        "num_wins": 6,
        "win_rate": 0.6,
        "abilities": [], "talents": [], "items_mid_late": [], "anchor_items": [],
        "sixslot": [], "neutral_stats": {}, "starting_items": [], "anchor_build_matches": [],
    }


class StratzStatsTests(unittest.TestCase):
    def test_one_detailed_response_produces_both_stat_datasets(self):
        popularity, detailed = normalize_stats([
            {"heroId": 1, "matchCount": 100, "winCount": 55, "kills": 8.2, "deaths": 5},
            {"heroId": 0, "matchCount": 1, "winCount": 1},
        ])
        self.assertEqual(popularity, [{"heroId": 1, "matchCount": 100, "winCount": 55}])
        self.assertEqual(detailed[0]["kills"], 8.2)
        self.assertIsNone(detailed[0]["assists"])

    def test_duplicate_hero_is_rejected(self):
        with self.assertRaisesRegex(DataShapeError, "duplicate"):
            normalize_stats([
                {"heroId": 1, "matchCount": 10, "winCount": 5},
                {"heroId": 1, "matchCount": 10, "winCount": 5},
            ])


class D2ptTests(unittest.TestCase):
    def test_browser_export_is_validated_and_copied(self):
        raw = {str(hero_id): {} for hero_id in HERO_IDS}
        raw["1"]["pos%201"] = _build()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "dota_builds.json"
            output = Path(directory) / "out.json"
            source.write_text(json.dumps(raw), encoding="utf-8")
            report = import_d2pt_builds(source=source, output=output)
            self.assertEqual(report["heroes"], len(HERO_IDS))
            self.assertEqual(report["populated_positions"], 1)
            self.assertTrue(output.exists())

    def test_invalid_win_rate_is_rejected(self):
        raw = {str(hero_id): {} for hero_id in HERO_IDS}
        raw["1"]["pos%201"] = {**_build(), "win_rate": 0.4}
        with self.assertRaisesRegex(DataShapeError, "disagrees"):
            validate_builds(raw)


if __name__ == "__main__":
    unittest.main()
