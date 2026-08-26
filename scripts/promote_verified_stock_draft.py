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
REQUIRED = (
    "id", "ticker", "title", "dek", "summary", "body", "context", "why",
    "watchNext", "sourceName", "sourceUrl", "timeLabel",
)


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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("draft")
    parser.add_argument("--max-age-minutes", type=int, default=90)
    args = parser.parse_args()

    draft = load(Path(args.draft))
    stocks = load(STOCKS_PATH)
    now = datetime.now(timezone.utc)

    if draft.get("status") != "VERIFIED_DRAFT":
        print("STOCK_FAILOVER_NOOP draft-not-verified")
        return 0
    created = parse_iso(draft.get("createdAt") or "")
    if created.astimezone(timezone.utc) > now + timedelta(minutes=2):
        raise SystemExit("verified draft createdAt is in the future")
    if now - created.astimezone(timezone.utc) > timedelta(minutes=args.max_age_minutes):
        print("STOCK_FAILOVER_NOOP draft-too-old")
        return 0

    try:
        current = parse_iso(stocks.get("generatedAt") or "")
    except Exception:
        current = datetime.min.replace(tzinfo=timezone.utc)
    if current.astimezone(timezone.utc) >= created.astimezone(timezone.utc):
        print("STOCK_FAILOVER_NOOP stocks-current")
        return 0

    tracked = list(stocks.get("tracked") or [])
    tickers = stocks.get("tickers") or {}
    candidates = [
        article for article in (draft.get("articles") or [])
        if isinstance(article, dict) and article.get("desk") == "stock-news"
    ]
    if not candidates:
        print("STOCK_FAILOVER_NOOP verified-draft-has-no-stock-news")
        return 0

    promoted = 0
    for source in candidates:
        for field in REQUIRED:
            if not clean(source.get(field)):
                raise SystemExit(f"verified stock draft missing {field}: {source.get('id')}")
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

        story = copy.deepcopy(source)
        story.pop("desk", None)
        story.pop("ticker", None)
        story["storyType"] = clean(story.get("storyType") or "VERIFIED NEWS")
        story["impact"] = impact_symbol(story.get("impact") or "")
        story["impactLabel"] = clean(story.get("impactLabel") or "VERIFIED UPDATE")

        old = tickers[ticker].get("stories") or []
        deduped = [
            item for item in old
            if isinstance(item, dict)
            and item.get("id") != story.get("id")
            and clean(item.get("sourceUrl")) != clean(story.get("sourceUrl"))
        ]
        tickers[ticker]["stories"] = [story] + deduped[:2]
        promoted += 1

    if promoted <= 0:
        print("STOCK_FAILOVER_NOOP no-tracked-stock-candidate")
        return 0

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
