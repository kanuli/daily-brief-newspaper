#!/usr/bin/env python3
import json
import pathlib
from datetime import datetime
from urllib.parse import urlparse

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "stocks-latest.json"
EXPECTED = ["NVDA", "AAPL", "TSM", "PLTR", "MSFT", "GOOG", "EMXC", "EWY", "VT"]
ETF_TICKERS = {"EMXC", "EWY", "VT"}
REQUIRED = [
    "id", "storyType", "impact", "impactLabel", "title", "dek", "summary",
    "body", "context", "why", "watchNext", "sourceName", "sourceUrl", "timeLabel"
]
VALID_IMPACTS = {"↑", "↓", "↔"}
VALID_COLLECTION_STATUS = {"COMPLETE", "INCOMPLETE", "COLLECTION_FAILURE"}


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


def valid_timestamp(value):
    if not text(value):
        return False
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.tzinfo is not None
    except Exception:
        return False


def main():
    require(PATH.exists(), "data/stocks-latest.json is missing")
    data = json.loads(PATH.read_text(encoding="utf-8"))
    require(data.get("mode") == "TRACKED_STOCK_NEWS", "mode must be TRACKED_STOCK_NEWS")
    require(data.get("tracked") == EXPECTED, f"tracked list must be exactly {EXPECTED}")
    require(valid_timestamp(data.get("generatedAt")), "generatedAt must be a timezone-aware ISO timestamp")
    require(text(data.get("lastUpdatedLabel")), "lastUpdatedLabel is required")

    # lastCheckedAt is deliberately distinct from generatedAt. It is optional for
    # legacy snapshots, but once the heartbeat exists its contract is validated.
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

        for i, story in enumerate(stories):
            label = f"{ticker}[{i}]"
            require(isinstance(story, dict), f"{label}: story must be object")
            for field in REQUIRED:
                require(text(story.get(field)), f"{label}: {field} is required")
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

    print(f"Stock News validation OK: {len(EXPECTED)} tickers, {len(seen)} stories")


if __name__ == "__main__":
    main()
