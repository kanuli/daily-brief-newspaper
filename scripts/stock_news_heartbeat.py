#!/usr/bin/env python3
"""Record an hourly Stock News newsroom check without faking story freshness.

The rolling discovery branch proves that the tracked-stock desk was searched.
This script records that check separately from ``generatedAt`` (the timestamp of
the most recent verified story publication). A check heartbeat never promotes
raw discovery candidates and never rewrites verified copy.

Stock discovery health is recalculated with strict ticker identity rules rather
than trusting the broad collector's raw count. This prevents examples such as
Virginia Tech (VT) or Navitas Semiconductor carrying a bad NVDA tag from making
the tracked-stock desk appear healthier than it really is.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_news_rules import match_tickers

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks-latest.json"
HKT = timezone(timedelta(hours=8))


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


def format_hkt(dt: datetime) -> str:
    local = dt.astimezone(HKT)
    return f"{local.year}年{local.month}月{local.day}日 {local.hour:02d}:{local.minute:02d} HKT"


def strict_candidates(staging: dict) -> tuple[list[dict], list[dict]]:
    desks = staging.get("desks") if isinstance(staging.get("desks"), dict) else {}
    stock_items = desks.get("stock-news") if isinstance(desks.get("stock-news"), list) else []
    valid = [
        item for item in stock_items
        if isinstance(item, dict)
        and match_tickers(item.get("title", ""), item.get("source", ""), item.get("query", ""))
    ]

    started_raw = staging.get("lastSearchStartedAt") or staging.get("lastSearchAt")
    try:
        started = parse_iso(started_raw)
    except Exception:
        return valid, []

    current: list[dict] = []
    for item in valid:
        try:
            last_seen = parse_iso(item.get("lastSeenAt") or "")
        except Exception:
            continue
        if abs((last_seen - started).total_seconds()) <= 3:
            current.append(item)
    return valid, current


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

    valid, current = strict_candidates(staging)
    floor = int(((staging.get("discoveryFloors") or {}).get("stock-news")) or 12)
    unique_this_run = len({str(item.get("id") or item.get("title")) for item in current})
    reservoir_count = len({str(item.get("id") or item.get("title")) for item in valid})
    floor_met = unique_this_run >= floor
    is_underfilled = reservoir_count < floor

    if unique_this_run <= 0:
        collection_status = "COLLECTION_FAILURE"
    elif not floor_met or is_underfilled:
        collection_status = "INCOMPLETE"
    else:
        collection_status = "COMPLETE"

    stocks["lastCheckedAt"] = checked.isoformat()
    stocks["lastCheckedLabel"] = format_hkt(checked)
    stocks["collectionStatus"] = collection_status
    stocks["collectionSource"] = "rolling-news-search+strict-ticker-filter"
    stocks["discoveryCandidateCount"] = reservoir_count
    stocks["discoveredThisCheck"] = unique_this_run
    stocks["discoveryFloorMet"] = floor_met
    stocks["discoveryUnderfilled"] = is_underfilled
    stocks["rawDiscoveryCandidateCount"] = int(((staging.get("candidateCounts") or {}).get("stock-news")) or 0)
    stocks["rejectedDiscoveryNoiseCount"] = max(0, stocks["rawDiscoveryCandidateCount"] - reservoir_count)
    stocks["verifiedContentUpdatedAt"] = stocks.get("generatedAt")
    stocks["freshnessContract"] = {
        "lastCheckedAt": "hourly newsroom/search heartbeat after strict tracked-ticker identity filtering; does not imply a new verified story",
        "generatedAt": "time the verified Stock News content last changed",
    }

    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "STOCK_HEARTBEAT_UPDATED",
        f"checked={checked.isoformat()}",
        f"status={collection_status}",
        f"strict_discovered={unique_this_run}",
        f"strict_reservoir={reservoir_count}",
        f"raw_reservoir={stocks['rawDiscoveryCandidateCount']}",
        f"rejected_noise={stocks['rejectedDiscoveryNoiseCount']}",
        f"floor_met={floor_met}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
