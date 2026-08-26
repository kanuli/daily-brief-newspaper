#!/usr/bin/env python3
"""Record an hourly Stock News newsroom check without faking story freshness.

The rolling discovery branch proves that the tracked-stock desk was searched.
This script records that check separately from ``generatedAt`` (the timestamp of
the most recent verified story publication). A check heartbeat never promotes
raw discovery candidates and never rewrites verified copy.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks-latest.json"
HKT = timezone(timedelta(hours=8))


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt


def format_hkt(dt: datetime) -> str:
    local = dt.astimezone(HKT)
    return f"{local.year}年{local.month}月{local.day}日 {local.hour:02d}:{local.minute:02d} HKT"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("staging")
    parser.add_argument("--min-interval-minutes", type=int, default=45)
    args = parser.parse_args()

    staging = load(Path(args.staging))
    stocks = load(STOCKS_PATH)

    if staging.get("mode") != "ROLLING_NEWS_DISCOVERY_STAGING":
        raise SystemExit("Stock heartbeat requires rolling discovery staging")

    checked = parse_iso(staging.get("lastSearchAt") or "")
    previous_raw = stocks.get("lastCheckedAt")
    if previous_raw:
        previous = parse_iso(previous_raw)
        if checked <= previous:
            print("STOCK_HEARTBEAT_NOOP staging-not-newer")
            return 0
        if checked - previous < timedelta(minutes=args.min_interval_minutes):
            print("STOCK_HEARTBEAT_NOOP minimum-interval-not-reached")
            return 0

    audit = (staging.get("queryAudit") or {}).get("stock-news") or {}
    counts = staging.get("candidateCounts") or {}
    underfilled = staging.get("underfilledDesks") or {}
    unique_this_run = int(audit.get("uniqueDiscoveredThisRun") or 0)
    reservoir_count = int(counts.get("stock-news") or 0)
    floor_met = bool(audit.get("floorMetThisRun"))
    is_underfilled = "stock-news" in underfilled

    if unique_this_run <= 0:
        collection_status = "COLLECTION_FAILURE"
    elif not floor_met or is_underfilled:
        collection_status = "INCOMPLETE"
    else:
        collection_status = "COMPLETE"

    stocks["lastCheckedAt"] = checked.isoformat()
    stocks["lastCheckedLabel"] = format_hkt(checked)
    stocks["collectionStatus"] = collection_status
    stocks["collectionSource"] = "rolling-news-search"
    stocks["discoveryCandidateCount"] = reservoir_count
    stocks["discoveredThisCheck"] = unique_this_run
    stocks["discoveryFloorMet"] = floor_met
    stocks["discoveryUnderfilled"] = is_underfilled
    stocks["verifiedContentUpdatedAt"] = stocks.get("generatedAt")
    stocks["freshnessContract"] = {
        "lastCheckedAt": "hourly newsroom/search heartbeat; does not imply a new verified story",
        "generatedAt": "time the verified Stock News content last changed",
    }

    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "STOCK_HEARTBEAT_UPDATED",
        f"checked={checked.isoformat()}",
        f"status={collection_status}",
        f"discovered={unique_this_run}",
        f"reservoir={reservoir_count}",
        f"floor_met={floor_met}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
