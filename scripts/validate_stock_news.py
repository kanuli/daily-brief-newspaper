#!/usr/bin/env python3
import json
import pathlib
import re
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "stocks-latest.json"
EXPECTED = ["GOOG", "GLDM", "ICE", "MCD", "EMXC", "GBTC", "DBA", "AAPL", "EWY", "META", "MSFT", "NVDA", "TSM", "PLTR", "VT"]
ETF_TICKERS = {"GLDM", "EMXC", "GBTC", "DBA", "EWY", "VT"}
REQUIRED = [
    "id", "storyType", "impact", "impactLabel", "title", "dek", "summary",
    "body", "context", "why", "watchNext", "sourceName", "sourceUrl", "timeLabel"
]
PUBLIC_COPY_FIELDS = ("title", "dek", "summary", "body", "context", "why", "watchNext")
BANNED_PUBLIC_FRAGMENTS = (
    "第一手資料已通過Stock News核實",
    "已通過Stock News核實",
    "Stock News核實",
    "Stock News 核實",
    "自動核實器",
    "本自動稿",
    "人工編輯核實稿",
    "自動速報",
    "第一手來源確認，不依賴市場轉述",
    "暫無新聞",
    "暫無新消息",
    "沒有新聞",
    "沒有新消息",
)
VALID_IMPACTS = {"↑", "↓", "↔"}
VALID_COLLECTION_STATUS = {"COMPLETE", "INCOMPLETE", "COLLECTION_FAILURE"}
MAX_SNAPSHOT_AGE_HOURS = 72
MAX_COVERAGE_CHECK_AGE_HOURS = 3.0
# A fresh source/editorial review is required every three hours, but review
# timestamps never refresh old public news. Every tracked symbol must still
# carry at least one substantive event or market read-through from the last
# 48 hours. This matches the heartbeat contract and fails closed on stale copy.
MAX_SUBSTANTIVE_STORY_AGE_HOURS = 48.0
SUBSTANTIVE_TIME_FIELDS = (
    "primaryPublishedAt", "sourcePublishedAt", "eventPublishedAt", "marketAsOfAt", "publishedAt"
)
ID_DATE_RE = re.compile(r"(?:^|[-_])(20\d{6})(?:$|[-_])")
HKT = ZoneInfo("Asia/Hong_Kong")


def require(cond, msg):
    if not cond:
        raise SystemExit(f"Stock News validation failed: {msg}")


def text(v):
    return isinstance(v, str) and bool(v.strip())


def valid_http_url(value):
    if not text(value):
        return False
    parsed = urlparse(value.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_timestamp(value):
    if not text(value):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo is not None else None
    except Exception:
        return None


def valid_timestamp(value):
    return parse_timestamp(value) is not None


def substantive_story_time(story):
    for field in SUBSTANTIVE_TIME_FIELDS:
        dt = parse_timestamp(story.get(field))
        if dt is not None:
            return dt.astimezone(timezone.utc), field

    # Legacy artifacts can encode only the real event calendar date in the
    # stable story id. Map that date to 00:00 HKT, not 23:59:59: start-of-day
    # deliberately overstates age and therefore cannot make an old story look
    # fresher. Display/check timestamps remain ineligible for freshness.
    match = ID_DATE_RE.search(str(story.get("id") or ""))
    if match:
        try:
            day = datetime.strptime(match.group(1), "%Y%m%d").date()
            start_hkt = datetime.combine(day, time(0, 0, 0), tzinfo=HKT)
            return start_hkt.astimezone(timezone.utc), "story-id-date"
        except Exception:
            pass
    return None, None


def main():
    require(PATH.exists(), "data/stocks-latest.json is missing")
    data = json.loads(PATH.read_text(encoding="utf-8"))
    require(data.get("mode") == "TRACKED_STOCK_NEWS", "mode must be TRACKED_STOCK_NEWS")
    require(data.get("tracked") == EXPECTED, f"tracked list must be exactly {EXPECTED}")

    generated = parse_timestamp(data.get("generatedAt"))
    require(generated is not None, "generatedAt must be a timezone-aware ISO timestamp")
    generated_utc = generated.astimezone(timezone.utc)
    now = datetime.now(timezone.utc)
    age_hours = (now - generated_utc).total_seconds() / 3600.0
    require(age_hours >= -1.0, "generatedAt must not be materially in the future")
    require(age_hours <= MAX_SNAPSHOT_AGE_HOURS,
            f"generatedAt is stale ({age_hours:.1f}h old; maximum {MAX_SNAPSHOT_AGE_HOURS}h)")
    require(text(data.get("lastUpdatedLabel")), "lastUpdatedLabel is required")

    quality = data.get("qualityGates") if isinstance(data.get("qualityGates"), dict) else {}
    stale_symbols = data.get("staleSymbols")
    freshness = data.get("coverageFreshness")
    require(isinstance(stale_symbols, list), "staleSymbols must be an array")
    require(isinstance(freshness, dict), "coverageFreshness must be an object")
    require(list(freshness.keys()) == EXPECTED, "coverageFreshness key order/set must match tracked list")
    require(quality.get("freshnessGateMet") is True,
            f"per-symbol currentness gate failed; staleSymbols={stale_symbols}")
    require(not stale_symbols, f"stale tracked-symbol coverage is not publishable: {stale_symbols}")

    checked = parse_timestamp(data.get("lastCheckedAt"))
    require(checked is not None, "lastCheckedAt is required and must be timezone-aware")
    checked_utc = checked.astimezone(timezone.utc)
    check_age = (now - checked_utc).total_seconds() / 3600.0
    require(check_age >= -1.0, "lastCheckedAt must not be materially in the future")
    require(check_age <= MAX_COVERAGE_CHECK_AGE_HOURS,
            f"source/editorial review is stale ({check_age:.1f}h; maximum {MAX_COVERAGE_CHECK_AGE_HOURS}h)")
    require(text(data.get("lastCheckedLabel")), "lastCheckedLabel is required when lastCheckedAt exists")
    require(str(data.get("collectionStatus") or "").upper() in VALID_COLLECTION_STATUS,
            f"collectionStatus must be one of {sorted(VALID_COLLECTION_STATUS)}")
    for field in ("discoveryCandidateCount", "discoveredThisCheck"):
        require(isinstance(data.get(field), int) and data[field] >= 0,
                f"{field} must be a non-negative integer when heartbeat exists")
    require(isinstance(data.get("discoveryFloorMet"), bool), "discoveryFloorMet must be boolean")
    require(isinstance(data.get("discoveryUnderfilled"), bool), "discoveryUnderfilled must be boolean")

    tickers = data.get("tickers")
    require(isinstance(tickers, dict), "tickers must be an object")
    require(list(tickers.keys()) == EXPECTED, "ticker key order/set must match tracked list")

    seen = set()
    for ticker in EXPECTED:
        block = tickers[ticker]
        require(text(block.get("name")), f"{ticker}: name is required")
        expected_asset_type = "ETF" if ticker in ETF_TICKERS else "EQUITY"
        require(block.get("assetType") == expected_asset_type,
                f"{ticker}: assetType must be {expected_asset_type}")
        stories = block.get("stories")
        require(isinstance(stories, list) and 1 <= len(stories) <= 3,
                f"{ticker}: stories must contain 1 to 3 verified items")

        row = freshness.get(ticker)
        require(isinstance(row, dict), f"{ticker}: coverageFreshness entry must be object")
        require(row.get("stale") is False, f"{ticker}: coverage is stale")
        require(row.get("reviewEvidenceFound") is True,
                f"{ticker}: authoritative fresh review was not completed")
        require(valid_timestamp(row.get("lastReviewedAt")),
                f"{ticker}: coverageFreshness.lastReviewedAt must be a timezone-aware timestamp")
        search_age = row.get("searchHoursAgo")
        if search_age is None:
            search_age = row.get("hoursAgo")
        require(isinstance(search_age, (int, float)) and search_age >= 0,
                f"{ticker}: coverageFreshness search age must be a non-negative number")
        require(search_age <= MAX_COVERAGE_CHECK_AGE_HOURS,
                f"{ticker}: coverage review is stale ({search_age:.1f}h; maximum {MAX_COVERAGE_CHECK_AGE_HOURS}h)")
        require(row.get("storyCount") == len(stories),
                f"{ticker}: coverageFreshness.storyCount must match published story count")

        substantive_ages = []
        for i, story in enumerate(stories):
            label = f"{ticker}[{i}]"
            require(isinstance(story, dict), f"{label}: story must be object")
            for field in REQUIRED:
                require(text(story.get(field)), f"{label}: {field} is required")
            for field in PUBLIC_COPY_FIELDS:
                public_text = str(story.get(field) or "")
                require(not any(fragment in public_text for fragment in BANNED_PUBLIC_FRAGMENTS),
                        f"{label}: {field} contains internal verification/process/no-news filler copy")
                require("no news" not in public_text.lower(), f"{label}: {field} contains no-news filler copy")
            require(story["id"] not in seen, f"duplicate story id {story['id']}")
            seen.add(story["id"])
            require(story["impact"] in VALID_IMPACTS,
                    f"{label}: impact must be one of {sorted(VALID_IMPACTS)}")
            if ticker in ETF_TICKERS:
                require("ETF READ-THROUGH" in story["storyType"].upper(),
                        f"{label}: ETF stories must be explicitly labelled ETF READ-THROUGH")

            body = story["body"].strip()
            require(len(body) >= 100, f"{label}: body must be at least 100 characters")
            require(len(body) <= 1200, f"{label}: body is too long for the 100–500 word/character editorial target")
            require("\n\n" in body, f"{label}: body must contain at least two paragraphs")
            require(valid_http_url(story["sourceUrl"]), f"{label}: sourceUrl must be an http(s) URL")

            sources = story.get("sources", [])
            require(isinstance(sources, list) and sources,
                    f"{label}: sources must contain at least one source")
            for j, source in enumerate(sources):
                require(isinstance(source, dict), f"{label}.sources[{j}] must be object")
                require(text(source.get("name")), f"{label}.sources[{j}].name is required")
                require(valid_http_url(source.get("url")),
                        f"{label}.sources[{j}].url must be an http(s) URL")

            substantive_dt, source_field = substantive_story_time(story)
            if substantive_dt is not None:
                story_age = (now - substantive_dt).total_seconds() / 3600.0
                if story_age >= -1.0:
                    substantive_ages.append((story_age, story.get("id"), source_field))

        require(substantive_ages,
                f"{ticker}: no story carries a real substantive timestamp/date")
        youngest_age, youngest_id, time_source = min(substantive_ages, key=lambda row: row[0])
        require(
            youngest_age <= MAX_SUBSTANTIVE_STORY_AGE_HOURS,
            f"{ticker}: newest substantive story/read-through is stale ({youngest_age:.1f}h old; maximum {MAX_SUBSTANTIVE_STORY_AGE_HOURS}h; story={youngest_id}; source={time_source}); a fresh review alone cannot refresh old content",
        )

    print(f"Stock News validation OK: {len(EXPECTED)} tickers, {len(seen)} stories; hard substantive per-symbol freshness OK")


if __name__ == "__main__":
    main()
