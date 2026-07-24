"""One local command which collects all currently supported D2Helper datasets."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from tools.stratz_collector.__main__ import collect_matchups
from tools.stratz_collector.aggregate import DataShapeError
from tools.stratz_collector.client import StratzRequestError

from .d2pt import import_d2pt_builds
from .stratz_stats import collect_hero_stats


logger = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect all D2Helper datasets locally and write one validation report."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd(),
                        help="Repository root containing the current data files (default: current directory).")
    parser.add_argument("--output-dir", type=Path, default=Path(".runtime/data-collector"),
                        help="Directory for generated artifacts and report.")
    parser.add_argument("--d2pt-input", type=Path, required=True,
                        help="dota_builds.json downloaded by the D2PT browser collector.")
    parser.add_argument("--token-env", default="STRATZ_API_TOKEN",
                        help="Environment variable containing the STRATZ token.")
    parser.add_argument("--endpoint", default="https://api.stratz.com/graphql",
                        help="STRATZ GraphQL endpoint.")
    parser.add_argument("--attempts", type=int, default=5,
                        help="Network / 429 / 5xx attempts per STRATZ request (default: 5).")
    parser.add_argument("--request-delay", type=float, default=0.8,
                        help="Pause between weekly matchup queries in seconds (default: .8).")
    return parser


async def _collect(args: argparse.Namespace) -> dict:
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise DataShapeError(f"environment variable {args.token_env} is not set")
    root = args.project_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stats = await collect_hero_stats(
        token=token,
        popularity_output=output_dir / "hero_stats.new.json",
        detailed_output=output_dir / "hero_detailed_stats.new.json",
        endpoint=args.endpoint,
        attempts=args.attempts,
    )
    matchups = await collect_matchups(
        token=token,
        reference_path=root / "hero_matchups.json",
        output_path=output_dir / "hero_matchups.new.json",
        endpoint=args.endpoint,
        attempts=args.attempts,
        request_delay=args.request_delay,
    )
    builds = import_d2pt_builds(
        source=args.d2pt_input,
        output=output_dir / "dota_builds.new.json",
    )
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "ok",
        "outputs": {
            "hero_stats": stats,
            "hero_detailed_stats": stats,
            "hero_matchups": {
                "heroes": matchups.hero_count,
                "pairs": matchups.pair_count,
                "total_match_count": matchups.total_matches,
                "low_sample_pairs": matchups.low_sample_pairs,
            },
            "dota_builds": builds,
        },
    }


def _write_report(path: Path, report: dict) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parser().parse_args()
    try:
        report = asyncio.run(_collect(args))
    except (DataShapeError, StratzRequestError, ValueError) as exc:
        logger.error("data collection stopped: %s", exc)
        return 1
    report_path = args.output_dir.resolve() / "collection-report.json"
    _write_report(report_path, report)
    logger.info("collection complete; report=%s", report_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
