"""CLI for collecting STRATZ safe, mid, and off lane outcomes locally."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from tools.stratz_collector.aggregate import DataShapeError
from tools.stratz_collector.client import StratzClient, StratzRequestError
from tools.stratz_collector.queries import STATS_QUERY
from tools.stratz_collector.validate import load_legacy_file
from tools.stratz_collector.weeks import completed_weeks_from_stats

from .aggregate import aggregate_snapshots, parse_rows, to_jsonable
from .models import LaneData
from .queries import LANE_ALIASES, LANE_OUTCOME_QUERY
from .validate import LaneValidationReport, validate_lane_data


logger = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect validated STRATZ lane outcomes into a standalone JSON artifact."
    )
    parser.add_argument("--hero-reference", required=True, type=Path,
                        help="Known-good hero_matchups.json used for the playable hero set.")
    parser.add_argument("--output", required=True, type=Path,
                        help="Destination written atomically after validation.")
    parser.add_argument("--weeks", type=int, default=3,
                        help="Number of completed STRATZ weeks to aggregate (default: 3).")
    parser.add_argument("--token-env", default="STRATZ_API_TOKEN",
                        help="Environment variable containing the STRATZ token.")
    parser.add_argument("--endpoint", default="https://api.stratz.com/graphql",
                        help="STRATZ GraphQL endpoint.")
    parser.add_argument("--attempts", type=int, default=5,
                        help="Network / 429 / 5xx attempts per request (default: 5).")
    parser.add_argument("--timeout", type=float, default=90.0,
                        help="Timeout per full laneOutcome request in seconds (default: 90).")
    parser.add_argument("--request-delay", type=float, default=0.8,
                        help="Pause between GraphQL requests in seconds (default: .8).")
    return parser


def _playable_hero_ids(reference_path: Path) -> set[str]:
    reference = load_legacy_file(reference_path)
    playable = {
        hero_id
        for hero_id, pairs in reference.items()
        if pairs["vs"] or pairs["with"]
    }
    if not playable:
        raise DataShapeError("hero reference contains no playable heroes")
    return playable


async def collect_lane_outcomes(
    *,
    token: str,
    hero_reference_path: Path,
    output_path: Path,
    weeks_count: int = 3,
    endpoint: str = "https://api.stratz.com/graphql",
    attempts: int = 5,
    timeout: float = 90.0,
    request_delay: float = 0.8,
) -> LaneValidationReport:
    token = token.strip()
    if not token:
        raise DataShapeError("STRATZ token is not set")
    if request_delay < 0:
        raise ValueError("request_delay must not be negative")
    hero_ids = _playable_hero_ids(hero_reference_path)
    client = StratzClient(
        token, endpoint=endpoint, attempts=attempts, timeout=timeout,
    )

    stats = await client.execute({"query": STATS_QUERY, "variables": {}})
    try:
        weeks = completed_weeks_from_stats(
            stats["data"]["heroStats"]["stats"], weeks_count,
        )
    except (KeyError, TypeError) as exc:
        raise DataShapeError("STRATZ stats response has an unexpected shape") from exc

    snapshots: list[LaneData] = []
    request_number = 0
    total_requests = len(weeks) * 2
    for week in weeks:
        snapshot: LaneData = {"with": {}, "against": {}}
        for mode, is_with in (("with", True), ("against", False)):
            if request_number:
                await asyncio.sleep(request_delay)
            request_number += 1
            logger.info(
                "collecting %s, STRATZ week %d: %d/%d",
                mode, week.number, request_number, total_requests,
            )
            response = await client.execute({
                "query": LANE_OUTCOME_QUERY,
                "variables": {"week": week.timestamp, "isWith": is_with},
            })
            try:
                hero_stats = response["data"]["heroStats"]
            except (KeyError, TypeError) as exc:
                raise DataShapeError(
                    f"STRATZ laneOutcome response has an unexpected shape for {mode}"
                ) from exc
            for alias, lane in LANE_ALIASES.items():
                try:
                    rows = hero_stats[alias]
                except (KeyError, TypeError) as exc:
                    raise DataShapeError(
                        f"STRATZ laneOutcome response is missing {lane} for {mode}"
                    ) from exc
                parsed = parse_rows(
                    rows,
                    hero_ids,
                    description=f"{mode}, {lane}, week {week.number}",
                    lane=lane,
                )
                snapshot[mode] = aggregate_snapshots([
                    {mode: snapshot[mode]},
                    {mode: parsed},
                ])[mode]
        snapshots.append(snapshot)

    candidate = aggregate_snapshots(snapshots)
    report = validate_lane_data(candidate, hero_ids)
    payload = {
        "metadata": {
            "source": "STRATZ heroStats.laneOutcome",
            "schemaVersion": 1,
            "generatedAt": datetime.now(UTC).isoformat(),
            "weeks": [
                {"number": week.number, "date": week.date}
                for week in weeks
            ],
            "lanes": {
                "SAFE": ["POSITION_1", "POSITION_5"],
                "MID": ["POSITION_2"],
                "OFF": ["POSITION_3", "POSITION_4"],
            },
            "rankBrackets": "all",
        },
        **to_jsonable(candidate),
    }
    _atomic_json_write(output_path, payload)
    return report


def _atomic_json_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False,
    ) as temp:
        json.dump(payload, temp, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        temp.write("\n")
        temporary_path = Path(temp.name)
    temporary_path.replace(path)


async def _collect(args: argparse.Namespace) -> None:
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        raise DataShapeError(f"environment variable {args.token_env} is not set")
    report = await collect_lane_outcomes(
        token=token,
        hero_reference_path=args.hero_reference,
        output_path=args.output,
        weeks_count=args.weeks,
        endpoint=args.endpoint,
        attempts=args.attempts,
        timeout=args.timeout,
        request_delay=args.request_delay,
    )
    logger.info(
        "saved %s: heroes=%d pairs=%d total_matchCount=%d low_samples=%d",
        args.output, report.hero_count, report.pair_count,
        report.total_matches, report.low_sample_pairs,
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parser().parse_args()
    try:
        asyncio.run(_collect(args))
    except (DataShapeError, StratzRequestError, ValueError) as exc:
        logger.error("lane collector stopped without changing the output: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
