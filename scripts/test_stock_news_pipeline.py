#!/usr/bin/env python3
"""Regression tests for strict Stock News verification rules."""
from __future__ import annotations

from datetime import datetime, timezone

from stock_news_rules import best_corroboration, match_tickers
from stock_verified_producer import PrimaryEvent, build_sec_article, select_articles


def blank_stocks() -> dict:
    return {
        "tracked": ["NVDA", "AAPL", "TSM", "PLTR", "MSFT", "GOOG", "EMXC", "EWY", "VT"],
        "tickers": {
            ticker: {"stories": []}
            for ticker in ["NVDA", "AAPL", "TSM", "PLTR", "MSFT", "GOOG", "EMXC", "EWY", "VT"]
        },
    }


def assert_required_story_shape(story: dict) -> None:
    for field in (
        "id", "ticker", "desk", "storyType", "impact", "impactLabel", "title", "dek",
        "summary", "body", "context", "why", "watchNext", "sourceName", "sourceUrl",
        "timeLabel", "sources",
    ):
        assert story.get(field), f"missing {field}"
    assert "\n\n" in story["body"]
    assert len(story["body"]) >= 100
    assert story["impact"] in {"↑", "↓", "↔"}


def main() -> int:
    # Known false positives observed in the production discovery reservoir.
    assert match_tickers("Navitas Semiconductor (NVDA) Tests Its Claros Deal Against An Undervalued Narrative", "Yahoo Finance", "stocks") == []
    assert match_tickers("Blacksburg police hold door-to-door meetings regarding VT game days", "WFXRtv", "tracked stock query") == []

    # Canonical company/fund identities still match.
    assert match_tickers("Nvidia posts quarterly results (NASDAQ:NVDA)", "Reuters", "earnings") == ["NVDA"]
    assert match_tickers("Apple announces product event date (AAPL:NASDAQ)", "Reuters", "product") == ["AAPL"]
    assert match_tickers("Vanguard Total World Stock ETF (VT) updates holdings", "Vanguard", "ETF") == ["VT"]
    assert match_tickers("TSMC monthly revenue report", "TSMC", "revenue") == ["TSM"]

    now = datetime(2026, 8, 27, 4, 43, 53, tzinfo=timezone.utc)
    official = PrimaryEvent(
        ticker="AAPL",
        event_type="product-event",
        title="Apple sets September event date",
        url="https://example.com/apple-official",
        source="Apple",
        published_at=now,
        summary="Special Apple Event September 9",
        event_id="fixture-aapl-event",
    )
    noisy = [
        {
            "title": "Apple event September 9 confirmed",
            "source": "Stocktwits",
            "url": "https://example.com/noisy",
            "query": "AAPL product",
        }
    ]
    assert best_corroboration("AAPL", official.title + " " + official.summary, noisy) is None
    articles, audit = select_articles([official], noisy, blank_stocks(), now)
    assert articles == [], audit

    trusted = [
        {
            "title": "Apple sets September 9 date for product launch event",
            "source": "Reuters",
            "url": "https://example.com/reuters-apple",
            "query": "AAPL product event",
        }
    ]
    assert best_corroboration("AAPL", official.title + " " + official.summary, trusted)
    articles, audit = select_articles([official], trusted, blank_stocks(), now)
    assert len(articles) == 1, audit
    assert_required_story_shape(articles[0])
    assert articles[0]["ticker"] == "AAPL"
    assert len(articles[0]["sources"]) == 2

    # SEC filings are primary regulatory evidence and do not require media
    # corroboration. They also must generate conservative neutral copy.
    sec_event = PrimaryEvent(
        ticker="MSFT",
        event_type="regulatory",
        title="Microsoft 8-K filing 2026-08-27",
        url="https://www.sec.gov/Archives/example-msft-8k.htm",
        source="U.S. SEC EDGAR",
        published_at=now,
        summary="",
        event_id="sec-msft-0001",
        facts={"form": "8-K", "filingDate": "2026-08-27", "accession": "0001"},
        channel="sec",
    )
    sec_story = build_sec_article(sec_event, now)
    assert_required_story_shape(sec_story)
    assert sec_story["impact"] == "↔"
    articles, audit = select_articles([sec_event], [], blank_stocks(), now)
    assert len(articles) == 1, audit

    # Existing source URLs are a hard duplicate block.
    duplicate = blank_stocks()
    duplicate["tickers"]["MSFT"]["stories"] = [{
        "id": "old",
        "sourceUrl": sec_event.url,
        "sources": [{"name": "SEC", "url": sec_event.url}],
    }]
    articles, audit = select_articles([sec_event], [], duplicate, now)
    assert articles == [], audit

    print("STOCK_NEWS_PIPELINE_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
