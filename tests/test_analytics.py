import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    create_engine,
)

from backend import stats_db
from backend.analytics_report import format_analytics_messages


NOW = datetime(2026, 7, 27, 12, tzinfo=timezone.utc)
DAY = NOW.replace(hour=0, minute=0, second=0, microsecond=0)


class AnalyticsOverviewTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        metadata = MetaData()
        self.user_profiles = Table(
            "user_profiles",
            metadata,
            Column("user_id", BigInteger, primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        self.events = Table(
            "analytics_events",
            metadata,
            Column("id", BigInteger, primary_key=True),
            Column("event", String(64), nullable=False),
            Column("user_id", BigInteger),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )
        metadata.create_all(self.engine)
        self._seed()

    def tearDown(self):
        self.engine.dispose()

    def _seed(self):
        cohort_day = DAY - timedelta(days=8)
        recent_day = DAY - timedelta(days=2)
        profiles = [
            {"user_id": 1, "created_at": cohort_day + timedelta(hours=8)},
            {"user_id": 2, "created_at": cohort_day + timedelta(hours=9)},
            {"user_id": 3, "created_at": cohort_day + timedelta(hours=10)},
            {"user_id": 4, "created_at": recent_day + timedelta(hours=11)},
        ]
        rows = []

        def event(name, user_id, created_at):
            rows.append({
                "id": len(rows) + 1,
                "event": name,
                "user_id": user_id,
                "created_at": created_at,
            })

        # Feature adoption on registration day.
        event("page_draft_battle", 1, cohort_day + timedelta(hours=8, minutes=5))
        event("page_draft_battle", 2, cohort_day + timedelta(hours=9, minutes=5))
        event("battle_queue", 1, cohort_day + timedelta(hours=8, minutes=10))
        event("battle_queue", 1, cohort_day + timedelta(hours=8, minutes=20))
        event("battle_queue", 2, cohort_day + timedelta(hours=9, minutes=10))
        event("battle_queue", 2, cohort_day + timedelta(hours=9, minutes=20))
        event("battle_start", 1, cohort_day + timedelta(hours=8, minutes=15))
        event("battle_start", 1, cohort_day + timedelta(hours=8, minutes=25))
        event("battle_start", 2, cohort_day + timedelta(hours=9, minutes=15))
        event("battle_finish", 1, cohort_day + timedelta(hours=8, minutes=45))
        event("battle_finish", 2, cohort_day + timedelta(hours=9, minutes=45))
        event("battle_afk", 2, cohort_day + timedelta(hours=9, minutes=30))
        event("battle_forfeit", 2, cohort_day + timedelta(hours=9, minutes=35))
        event("page_drafter", 3, cohort_day + timedelta(hours=10, minutes=5))
        event("page_minigame_hl", 4, recent_day + timedelta(hours=11, minutes=5))

        # Return activity: user 1 returns on D1 and D7, user 3 only on D1,
        # user 4 on D1. User 2 never returns.
        event("page_home", 1, cohort_day + timedelta(days=1, hours=8))
        event("page_home", 1, cohort_day + timedelta(days=1, hours=9))
        event("page_home", 3, cohort_day + timedelta(days=1, hours=10))
        # Opening a feature after registration day does not count as day-0 adoption.
        event("page_database", 1, cohort_day + timedelta(days=1, hours=11))
        event("page_home", 1, cohort_day + timedelta(days=7, hours=8))
        event("page_home", 4, recent_day + timedelta(days=1, hours=11))

        with self.engine.begin() as conn:
            conn.execute(self.user_profiles.insert(), profiles)
            conn.execute(self.events.insert(), rows)

    def test_overview_includes_usage_funnel_and_feature_retention(self):
        with (
            patch.object(stats_db, "engine", self.engine),
            patch("backend.stats_db.datetime") as mocked_datetime,
        ):
            mocked_datetime.now.return_value = NOW
            overview = stats_db.get_analytics_overview(days=30)

        features = {row["event"]: row for row in overview["features"]}
        self.assertEqual(features["battle_start"]["opens"], 3)
        self.assertEqual(features["battle_start"]["users"], 2)
        self.assertEqual(features["battle_start"]["opens_per_user"], 1.5)

        funnel = overview["battle_funnel"]
        self.assertEqual(funnel["queue_to_start_pct"], 75.0)
        self.assertEqual(funnel["start_to_finish_pct"], 66.7)
        self.assertEqual(funnel["afk_per_start_pct"], 33.3)
        self.assertEqual(funnel["forfeit_per_start_pct"], 33.3)

        retention = {
            row["event"]: row
            for row in overview["feature_retention"]
        }
        self.assertEqual(retention["battle_start"]["d1"]["users"], 2)
        self.assertEqual(retention["battle_start"]["d1"]["retained"], 1)
        self.assertEqual(retention["battle_start"]["d1"]["pct"], 50.0)
        self.assertEqual(retention["battle_start"]["d7"]["pct"], 50.0)
        self.assertEqual(retention["page_drafter"]["d1"]["pct"], 100.0)
        self.assertEqual(retention["page_drafter"]["d7"]["pct"], 0.0)
        self.assertIsNone(retention["page_database"]["d1"]["pct"])
        self.assertEqual(retention["page_minigame_hl"]["d1"]["pct"], 100.0)
        self.assertIsNone(retention["page_minigame_hl"]["d7"]["pct"])


class AnalyticsReportTests(unittest.TestCase):
    def test_report_is_split_and_labels_new_metrics(self):
        daily = [
            {"day": f"2026-day-{day:02d}", "dau": 100, "new": 20, "returning": 80}
            for day in range(1, 61)
        ]
        features = [
            {
                "event": "page_minigame_hl",
                "opens": 150,
                "users": 100,
                "opens_per_user": 1.5,
            },
            {
                "event": "battle_start",
                "opens": 80,
                "users": 50,
                "opens_per_user": 1.6,
            },
        ]
        analytics = {
            "daily": daily,
            "features": features,
            "support_clicks": 12,
            "battle_funnel": {
                "steps": [
                    {"event": "battle_start", "opens": 80, "users": 50},
                    {"event": "battle_finish", "opens": 72, "users": 48},
                ],
                "queue_to_start_pct": 95.5,
                "start_to_finish_pct": 90.0,
                "afk_per_start_pct": 2.5,
                "forfeit_per_start_pct": 1.2,
            },
            "retention_d1": {"avg_pct": 26, "cohorts": 14},
            "retention_d7": {"avg_pct": 6, "cohorts": 21},
            "feature_retention": [{
                "event": "battle_start",
                "d1": {"users": 100, "retained": 35, "pct": 35.0},
                "d7": {"users": 80, "retained": 10, "pct": 12.5},
            }],
        }

        messages = format_analytics_messages(analytics, days=60)

        self.assertEqual(len(messages), 2)
        self.assertTrue(all(len(message) < 4096 for message in messages))
        self.assertIn("1.5/юз.", messages[1])
        self.assertIn("очередь → старт: 95.5%", messages[1])
        self.assertIn("Битва — началась: D1 35% (35/100)", messages[1])
        self.assertIn("Больше / Меньше", messages[1])


if __name__ == "__main__":
    unittest.main()
