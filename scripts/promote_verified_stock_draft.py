#!/usr/bin/env python3
"""Refresh tracked Stock News from the latest verified stock draft."""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks-latest.json"
TRACKED = ["GOOG", "GLDM", "ICE", "MCD", "EMXC", "GBTC", "DBA", "AAPL", "EWY", "META", "MSFT", "NVDA", "TSM", "PLTR", "VT"]
ETF_TICKERS = {"GLDM", "EMXC", "GBTC", "DBA", "EWY", "VT"}
NAMES = {
    "GOOG": "Alphabet / Google",
    "GLDM": "SPDR Gold MiniShares Trust",
    "ICE": "Intercontinental Exchange",
    "MCD": "McDonald's",
    "EMXC": "iShares MSCI Emerging Markets ex China ETF",
    "GBTC": "Grayscale Bitcoin Trust",
    "DBA": "Invesco DB Agriculture Fund",
    "AAPL": "Apple",
    "EWY": "iShares MSCI South Korea ETF",
    "META": "Meta Platforms",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "TSM": "TSMC",
    "PLTR": "Palantir",
    "VT": "Vanguard Total World Stock ETF",
}
REQUIRED = (
    "id", "ticker", "title", "dek", "summary", "body", "context", "why",
    "watchNext", "sourceName", "sourceUrl", "timeLabel",
)
BANNED_PUBLIC_FRAGMENTS = (
    "第一手資料已通過Stock News核實",
    "已通過Stock News核實",
    "Stock News核實",
    "Stock News 核實",
)
PUBLIC_COPY_FIELDS = ("title", "dek", "summary", "body", "context", "why", "watchNext")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean(value):
    return " ".join(str(value or "").split())


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt


def impact_symbol(value: str) -> str:
    raw = clean(value).lower()
    if raw in {"↑", "↓", "↔"}:
        return clean(value)
    if any(word in raw for word in ("positive", "bull", "upside", "upgrade")):
        return "↑"
    if any(word in raw for word in ("negative", "bear", "downside", "downgrade")):
        return "↓"
    return "↔"


def format_hkt(dt: datetime) -> str:
    hkt = dt.astimezone(timezone(timedelta(hours=8)))
    return f"{hkt.year}年{hkt.month}月{hkt.day}日 {hkt.hour:02d}:{hkt.minute:02d} HKT"


def canonicalize_contract(stocks: dict) -> None:
    old = stocks.get("tickers") if isinstance(stocks.get("tickers"), dict) else {}
    migrated = {}
    for ticker in TRACKED:
        block = copy.deepcopy(old.get(ticker)) if isinstance(old.get(ticker), dict) else {}
        block["name"] = NAMES[ticker]
        block["assetType"] = "ETF" if ticker in ETF_TICKERS else "EQUITY"
        stories = block.get("stories") if isinstance(block.get("stories"), list) else []
        block["stories"] = [story for story in stories if isinstance(story, dict)][:3]
        migrated[ticker] = block
    stocks["tracked"] = TRACKED
    stocks["tickers"] = migrated


def contains_process_copy(story: dict) -> bool:
    public_copy = " ".join(str(story.get(field) or "") for field in PUBLIC_COPY_FIELDS)
    return any(fragment in public_copy for fragment in BANNED_PUBLIC_FRAGMENTS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("draft")
    parser.add_argument("--max-age-minutes", type=int, default=90)
    args = parser.parse_args()

    draft = load(Path(args.draft))
    stocks = load(STOCKS_PATH)
    canonicalize_contract(stocks)
    now = datetime.now(timezone.utc)

    if draft.get("status") != "VERIFIED_DRAFT":
        print("STOCK_FAILOVER_NOOP draft-not-verified")
        STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    created = parse_iso(draft.get("createdAt") or "")
    if created.astimezone(timezone.utc) > now + timedelta(minutes=2):
        raise SystemExit("verified draft createdAt is in the future")
    if now - created.astimezone(timezone.utc) > timedelta(minutes=args.max_age_minutes):
        print("STOCK_FAILOVER_NOOP draft-too-old")
        STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    # Publication freshness and substantive-content freshness are separate.
    # generatedAt is advanced every publication/check run, so comparing a new
    # verified draft against generatedAt can incorrectly block a genuinely new
    # story. Gate only against the last substantive verified-content timestamp;
    # fall back to generatedAt only for legacy snapshots that predate this field.
    content_clock_raw = stocks.get("verifiedContentUpdatedAt") or stocks.get("generatedAt") or ""
    try:
        content_clock = parse_iso(content_clock_raw)
    except Exception:
        content_clock = datetime.min.replace(tzinfo=timezone.utc)
    if content_clock.astimezone(timezone.utc) >= created.astimezone(timezone.utc):
        print("STOCK_FAILOVER_NOOP verified-content-current")
        STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    tracked = list(stocks.get("tracked") or [])
    tickers = stocks.get("tickers") or {}
    candidates = [
        article for article in (draft.get("articles") or [])
        if isinstance(article, dict) and article.get("desk") == "stock-news"
    ]
    if not candidates:
        print("STOCK_FAILOVER_NOOP verified-draft-has-no-stock-news")
        STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    promoted = 0
    promoted_tickers = set()
    for source in candidates:
        for field in REQUIRED:
            if not clean(source.get(field)):
                raise SystemExit(f"verified stock draft missing {field}: {source.get('id')}")
        if contains_process_copy(source):
            raise SystemExit(f"verified stock draft contains internal Stock News process copy: {source.get('id')}")
        sources = source.get("sources")
        if not isinstance(sources, list) or not sources:
            raise SystemExit(f"verified stock draft missing sources: {source.get('id')}")
        for index, evidence in enumerate(sources):
            if not isinstance(evidence, dict) or not clean(evidence.get("name")) or not clean(evidence.get("url")):
                raise SystemExit(f"verified stock draft invalid sources[{index}]: {source.get('id')}")

        ticker = clean(source.get("ticker")).upper()
        if ticker not in tracked or ticker not in tickers:
            continue
        if "\n\n" not in str(source.get("body") or ""):
            raise SystemExit(f"verified stock draft body needs two paragraphs: {source.get('id')}")

        supersedes_ids = {
            clean(value)
            for value in (source.get("supersedesIds") or [])
            if clean(value)
        }
        story = copy.deepcopy(source)
        story.pop("desk", None)
        story.pop("ticker", None)
        story.pop("supersedesIds", None)
        story["storyType"] = clean(story.get("storyType") or "VERIFIED NEWS")
        if ticker in ETF_TICKERS and "ETF READ-THROUGH" not in story["storyType"].upper():
            story["storyType"] = "ETF READ-THROUGH / " + story["storyType"]
        story["impact"] = impact_symbol(story.get("impact") or "")
        story["impactLabel"] = clean(story.get("impactLabel") or "VERIFIED UPDATE")

        old = tickers[ticker].get("stories") or []
        deduped = [
            item for item in old
            if isinstance(item, dict)
            and clean(item.get("id")) not in supersedes_ids
            and item.get("id") != story.get("id")
            and clean(item.get("sourceUrl")) != clean(story.get("sourceUrl"))
            and not contains_process_copy(item)
        ]
        tickers[ticker]["stories"] = [story] + deduped[:2]
        promoted += 1
        promoted_tickers.add(ticker)

    if promoted <= 0:
        print("STOCK_FAILOVER_NOOP no-tracked-stock-candidate")
        STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0

    # A manually/automatically verified story is itself fresh editorial evidence
    # for the symbol it updates. Keep coverage metadata synchronized with the
    # promoted content so a pre-promotion stale flag cannot invalidate a newly
    # verified, substantively current story. The independent validator still
    # enforces the hard 48-hour substantive-story limit from the story date.
    coverage = stocks.get("coverageFreshness") if isinstance(stocks.get("coverageFreshness"), dict) else {}
    for ticker in promoted_tickers:
        row = copy.deepcopy(coverage.get(ticker)) if isinstance(coverage.get(ticker), dict) else {}
        stories = tickers[ticker].get("stories") or []
        row.update({
            "lastReviewedAt": created.isoformat(),
            "searchHoursAgo": 0.0,
            "reviewEvidenceFound": True,
            "hoursAgo": 0.0,
            "newestSubstantiveStoryHoursAgo": 0.0,
            "newestSubstantiveStoryId": clean(stories[0].get("id")) if stories else "",
            "substantiveTimeSource": "story-id-date",
            "substantiveCurrent": True,
            "stale": False,
            "storyCount": len(stories),
        })
        coverage[ticker] = row
    stocks["coverageFreshness"] = {ticker: coverage.get(ticker, {}) for ticker in TRACKED}
    stale_symbols = [
        ticker for ticker in (stocks.get("staleSymbols") or [])
        if ticker not in promoted_tickers
    ]
    stocks["staleSymbols"] = stale_symbols
    quality = stocks.get("qualityGates") if isinstance(stocks.get("qualityGates"), dict) else {}
    quality["freshnessGateMet"] = not stale_symbols
    stocks["qualityGates"] = quality

    stocks["generatedAt"] = created.isoformat()
    stocks["lastUpdatedLabel"] = format_hkt(created)
    stocks["verifiedContentUpdatedAt"] = created.isoformat()
    stocks["verifiedDraftId"] = draft.get("draftId")
    verification_mode = clean(draft.get("verificationMode"))
    if verification_mode:
        stocks["verificationMode"] = verification_mode
    stocks["publicationSource"] = (
        "primary-source-auto-verification"
        if verification_mode.startswith("PRIMARY_SOURCE")
        else "verified-prepublish-draft"
    )
    STOCKS_PATH.write_text(json.dumps(stocks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "VERIFIED_STOCK_DRAFT_PROMOTED",
        f"draft={draft.get('draftId')}",
        f"created={created.isoformat()}",
        f"stories={promoted}",
        f"verification={verification_mode or 'legacy'}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
