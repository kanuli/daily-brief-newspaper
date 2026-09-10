#!/usr/bin/env python3
"""Record Stock News publication/search freshness without rewriting old events as new.

A fresh symbol-specific review is necessary but is not sufficient publication
freshness. Every tracked symbol must also carry at least one genuinely current
substantive event or market read-through. Review/check/display timestamps never
refresh an old public story.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from stock_news_rules import match_tickers

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks-latest.json"
HKT = timezone(timedelta(hours=8))
TRACKED = ["GOOG", "GLDM", "ICE", "MCD", "EMXC", "GBTC", "DBA", "AAPL", "EWY", "META", "MSFT", "NVDA", "TSM", "PLTR", "VT"]
MAX_COVERAGE_CHECK_AGE_HOURS = 3.0
MAX_SUBSTANTIVE_STORY_AGE_HOURS = 48.0
SUBSTANTIVE_TIME_FIELDS = (
    "primaryPublishedAt", "sourcePublishedAt", "eventPublishedAt", "marketAsOfAt", "publishedAt"
)
ID_DATE_RE = re.compile(r"(?:^|[-_])(20\d{6})(?:$|[-_])")


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


def substantive_story_time(story: dict) -> tuple[datetime | None, str | None]:
    for field in SUBSTANTIVE_TIME_FIELDS:
        try:
            return parse_iso(story.get(field) or ""), field
        except Exception:
            pass

    # Conservative compatibility for legacy stories whose stable id encodes the
    # real event date. Use the end of that HKT calendar day so this fallback never
    # invents intraday precision. Check/display timestamps are intentionally absent.
    match = ID_DATE_RE.search(str(story.get("id") or ""))
    if match:
        try:
            day = datetime.strptime(match.group(1), "%Y%m%d").date()
            end_hkt = datetime.combine(day, time(23, 59, 59), tzinfo=HKT)
            return end_hkt.astimezone(timezone.utc), "story-id-date"
        except Exception:
            pass
    return None, None


def newest_substantive_story(stories: list[dict], published: datetime) -> tuple[float | None, str | None, str | None]:
    candidates: list[tuple[float, str | None, str | None]] = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        dt, source = substantive_story_time(story)
        if dt is None:
            continue
        age = (published - dt).total_seconds() / 3600.0
        if age >= -1.0:
            candidates.append((max(0.0, age), story.get("id"), source))
    return min(candidates, key=lambda row: row[0]) if candidates else (None, None, None)


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


def reviewed_symbols(staging: dict, current: list[dict]) -> set[str]:
    found: set[str] = set()
    for item in current:
        found.update(match_tickers(item.get("title", ""), item.get("source", ""), item.get("query", "")))

    audit = staging.get("queryAudit") if isinstance(staging.get("queryAudit"), dict) else {}
    stock_audit = audit.get("stock-news") if isinstance(audit.get("stock-news"), dict) else {}
    try:
        planned_queries = int(stock_audit.get("queries") or 0)
    except Exception:
        planned_queries = 0
    if planned_queries >= len(TRACKED):
        found.update(TRACKED)
    return found


def refresh_coverage_freshness(stocks: dict, published: datetime, reviewed: set[str]) -> None:
    checked_raw = stocks.get("lastCheckedAt")
    try:
        checked = parse_iso(checked_raw) if checked_raw else None
    except Exception:
        checked = None

    check_age = float("inf") if checked is None else max(0.0, (published - checked).total_seconds() / 3600.0)
    search_current = checked is not None and check_age <= MAX_COVERAGE_CHECK_AGE_HOURS

    tickers = stocks.get("tickers") if isinstance(stocks.get("tickers"), dict) else {}
    freshness: dict[str, dict] = {}
    stale_symbols: list[str] = []
    for ticker in TRACKED:
        block = tickers.get(ticker) if isinstance(tickers.get(ticker), dict) else {}
        stories = block.get("stories") if isinstance(block.get("stories"), list) else []
        review_evidence = ticker in reviewed
        substantive_age, substantive_story_id, substantive_time_source = newest_substantive_story(stories, published)
        substantive_current = substantive_age is not None and substantive_age <= MAX_SUBSTANTIVE_STORY_AGE_HOURS
        stale = (not stories) or (not search_current) or (not review_evidence) or (not substantive_current)
        if stale:
            stale_symbols.append(ticker)

        freshness[ticker] = {
            "lastReviewedAt": checked.isoformat() if checked is not None else None,
            "searchHoursAgo": round(check_age, 3) if check_age != float("inf") else 999999.0,
            "reviewEvidenceFound": review_evidence,
            "hoursAgo": round(check_age, 3) if check_age != float("inf") else 999999.0,
            "newestSubstantiveStoryHoursAgo": round(substantive_age, 3) if substantive_age is not None else None,
            "newestSubstantiveStoryId": substantive_story_id,
            "substantiveTimeSource": substantive_time_source,
            "substantiveCurrent": substantive_current,
            "stale": stale,
            "storyCount": len(stories),
        }

    stocks["coverageFreshness"] = freshness
    stocks["staleSymbols"] = stale_symbols
    quality = stocks.get("qualityGates") if isinstance(stocks.get("qualityGates"), dict) else {}
    quality["freshnessGateMet"] = not stale_symbols
    stocks["qualityGates"] = quality


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
    valid, current = strict_candidates(staging)
    current_reviewed = reviewed_symbols(staging, current)

    previous_raw = stocks.get("lastCheckedAt")
    refresh_collection = True
    refresh_reason = "new-search-snapshot"
    if previous_raw:
        previous = parse_iso(previous_raw)
        if checked <= previous:
            refresh_collection = False
            refresh_reason = "staging-not-newer"
        elif checked - previous < timedelta(minutes=args.min_interval_minutes):
            refresh_collection = False
            refresh_reason = "minimum-interval-not-reached"

    previous_verified_update = stocks.get("verifiedContentUpdatedAt") or stocks.get("generatedAt")
    published = datetime.now(timezone.utc)
    stocks["generatedAt"] = published.isoformat()
    stocks["lastUpdatedLabel"] = format_hkt(published)
    stocks["verifiedContentUpdatedAt"] = previous_verified_update
    stocks["freshnessContract"] = {
        "generatedAt": "actual completion time of the current Stock News publication check",
        "verifiedContentUpdatedAt": "time the verified story set last changed",
        "lastCheckedAt": "source-search time after authoritative 15-symbol Stock collection",
        "coverageFreshness": "per-symbol fresh review plus at least one genuinely current substantive event or market read-through",
        "maxCoverageCheckAgeHours": MAX_COVERAGE_CHECK_AGE_HOURS,
        "maxSubstantiveStoryAgeHours": MAX_SUBSTANTIVE_STORY_AGE_HOURS,
        "substantiveTimeFields": list(SUBSTANTIVE_TIME_FIELDS),
        "legacyStoryIdDateFallback": True,
        "reviewRule": "a fresh review cannot make stale substantive content current",
        "schemaRule": "freshness metadata does not add or fabricate event timestamps on public stories",
    }

    if refresh_collection:
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
        stocks["collectionSource"] = "rolling-news-search+authoritative-15-symbol-plan"
        stocks["discoveryCandidateCount"] = reservoir_count
        stocks["discoveredThisCheck"] = unique_this_run
        stocks["discoveryFloorMet"] = floor_met
        stocks["discoveryUnderfilled"] = is_underfilled
        stocks["rawDiscoveryCandidateCount"] = int(((staging.get("candidateCounts") or {}).get("stock-news")) or 0)
        stocks["rejectedDiscoveryNoiseCount"] = max(0, stocks["rawDiscoveryCandidateCount"] - reservoir_count)

        message = (
            "STOCK_HEARTBEAT_UPDATED "
            f"published={published.isoformat()} checked={checked.isoformat()} "
            f"status={collection_status} strict_discovered={unique_this_run} "
            f"strict_reservoir={reservoir_count} reviewed_symbols={len(current_reviewed)} "
            f"raw_reservoir={stocks['rawDiscoveryCandidateCount']} "
            f"rejected_noise={stocks['rejectedDiscoveryNoiseCount']} floor_met={floor_met}"
        )
    else:
        message = (
            "STOCK_HEARTBEAT_PUBLICATION_REFRESHED "
            f"published={published.isoformat()} collection_refresh={refresh_reason} "
            f"last_checked={stocks.get('lastCheckedAt')} reviewed_symbols={len(current_reviewed)}"
        )

    refresh_coverage_freshness(stocks, published, current_reviewed)
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(message)
    if stocks.get("staleSymbols"):
        print("STOCK_COVERAGE_FRESHNESS_FAIL", ",".join(stocks["staleSymbols"]))
    else:
        print("STOCK_COVERAGE_FRESHNESS_PASS", len(TRACKED), "symbols")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
