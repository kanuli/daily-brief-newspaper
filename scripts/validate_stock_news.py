#!/usr/bin/env python3
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "stocks-latest.json"
EXPECTED = ["NVDA", "AAPL", "TSM", "PLTR", "MSFT", "GOOG", "EMXC", "EWY", "VT"]
REQUIRED = ["id", "storyType", "title", "dek", "summary", "body", "context", "why", "watchNext", "sourceName", "sourceUrl", "timeLabel"]


def require(cond, msg):
    if not cond:
        raise SystemExit(f"Stock News validation failed: {msg}")


def text(v):
    return isinstance(v, str) and bool(v.strip())


def main():
    require(PATH.exists(), "data/stocks-latest.json is missing")
    data = json.loads(PATH.read_text(encoding="utf-8"))
    require(data.get("mode") == "TRACKED_STOCK_NEWS", "mode must be TRACKED_STOCK_NEWS")
    require(data.get("tracked") == EXPECTED, f"tracked list must be exactly {EXPECTED}")
    require(text(data.get("generatedAt")), "generatedAt is required")
    tickers = data.get("tickers")
    require(isinstance(tickers, dict), "tickers must be an object")
    require(list(tickers.keys()) == EXPECTED, "ticker key order/set must match tracked list")

    seen = set()
    for ticker in EXPECTED:
        block = tickers[ticker]
        require(text(block.get("name")), f"{ticker}: name is required")
        require(block.get("assetType") in {"EQUITY", "ETF"}, f"{ticker}: assetType must be EQUITY or ETF")
        stories = block.get("stories")
        require(isinstance(stories, list) and stories, f"{ticker}: at least one verified story is required")
        for i, story in enumerate(stories):
            label = f"{ticker}[{i}]"
            require(isinstance(story, dict), f"{label}: story must be object")
            for field in REQUIRED:
                require(text(story.get(field)), f"{label}: {field} is required")
            require(story["id"] not in seen, f"duplicate story id {story['id']}")
            seen.add(story["id"])
            body = story["body"].strip()
            require(len(body) >= 100, f"{label}: body must be at least 100 characters")
            require("\n\n" in body, f"{label}: body must contain at least two paragraphs")
            sources = story.get("sources", [])
            require(isinstance(sources, list) and sources, f"{label}: sources must contain at least one source")
            for j, source in enumerate(sources):
                require(isinstance(source, dict), f"{label}.sources[{j}] must be object")
                require(text(source.get("name")) and text(source.get("url")), f"{label}.sources[{j}] requires name/url")

    print(f"Stock News validation OK: {len(EXPECTED)} tickers, {len(seen)} stories")


if __name__ == "__main__":
    main()
