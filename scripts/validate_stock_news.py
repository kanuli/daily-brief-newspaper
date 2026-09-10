#!/usr/bin/env python3
import json
import pathlib
from datetime import datetime, timezone
from urllib.parse import urlparse

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
)
VALID_IMPACTS = {"↑", "↓", "↔"}
VALID_COLLECTION_STATUS = {"COMPLETE", "INCOMPLETE", "COLLECTION_FAILURE"}
MAX_SNAPSHOT_AGE_HOURS = 72
MAX_STORY_AGE_HOURS = 36
SUBSTANTIVE_TIME_FIELDS = (
    "primaryPublishedAt",
    "sourcePublishedAt",
    "eventPublishedAt",
    "marketAsOfAt",
    "publishedAt",
)


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


def story_substantive_time(story):
    values = []
    for field in SUBSTANTIVE_TIME_FIELDS:
        dt = parse_timestamp(story.get(field))
        if dt is not None:
            values.append(dt.astimezone(timezone.utc))
    return max(values) if values else None


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
            f"per-symbol substantive freshness gate failed; staleSymbols={stale_symbols}")
    require(not stale_symbols, f"stale tracked symbols are not publishable: {stale_symbols}")

    if data.get("lastCheckedAt") is not None:
        require(valid_timestamp(data.get("lastCheckedAt")), "lastCheckedAt must be a timezone-aware ISO timestamp")
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

        substantive = []
        for i, story in enumerate(stories):
            label = f"{ticker}[{i}]"
            require(isinstance(story, dict), f"{label}: story must be object")
            for field in REQUIRED:
                require(text(story.get(field)), f"{label}: {field} is required")
            for field in PUBLIC_COPY_FIELDS:
                public_text = str(story.get(field) or "")
                require(not any(fragment in public_text for fragment in BANNED_PUBLIC_FRAGMENTS),
                        f"{label}: {field} contains internal verification/process copy")
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

            event_time = story_substantive_time(story)
            if event_time is not None:
                substantive.append(event_time)

        require(substantive,
                f"{ticker}: no story carries a real substantive timestamp ({', '.join(SUBSTANTIVE_TIME_FIELDS)})")
        newest = max(substantive)
        substantive_age = (now - newest).total_seconds() / 3600.0
        require(substantive_age >= -1.0, f"{ticker}: substantive timestamp is materially in the future")
        require(substantive_age <= MAX_STORY_AGE_HOURS,
                f"{ticker}: newest substantive story/read-through is stale ({substantive_age:.1f}h; maximum {MAX_STORY_AGE_HOURS}h)")

        row = freshness.get(ticker)
        require(isinstance(row, dict), f"{ticker}: coverageFreshness entry must be object")
        require(row.get("stale") is False, f"{ticker}: substantive content is stale")
        require(text(row.get("newestSubstantiveAt")), f"{ticker}: coverageFreshness.newestSubstantiveAt is required")
        require(isinstance(row.get("hoursAgo"), (int, float)) and row.get("hoursAgo") >= 0,
                f"{ticker}: coverageFreshness.hoursAgo must be a non-negative number")

    print(f"Stock News validation OK: {len(EXPECTED)} tickers, {len(seen)} stories; substantive freshness OK")


if __name__ == "__main__":
    main()
