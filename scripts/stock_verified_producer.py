#!/usr/bin/env python3
"""Build a Stock News VERIFIED_DRAFT from primary sources only.

Why this exists
---------------
The 15-minute rolling collector is intentionally a broad discovery reservoir.
It must never publish raw headlines.  This producer closes the missing middle
step for Stock News without using a paid API or an opaque AI writer:

1. editor-verified, expiring primary-source seeds;
2. official company RSS feeds;
3. material SEC filings for tracked issuers;
4. optional corroboration from trusted discovery sources.

Only first-party/regulatory evidence can create a draft.  A Reuters/CNBC/etc.
headline can corroborate an official event, but cannot create one by itself.
The resulting draft is consumed by promote_verified_stock_draft.py, which
retains the existing final schema/validation gate.
"""
from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from stock_news_rules import TRACKED, best_corroboration, classify_event, match_tickers, normalize

ROOT = Path(__file__).resolve().parents[1]
STOCKS_PATH = ROOT / "data" / "stocks-latest.json"
SEEDS_PATH = ROOT / "data" / "stock-verified-seeds.json"
HKT = timezone(timedelta(hours=8))
USER_AGENT = "DailyBriefStockVerifier/1.0 (+https://github.com/kanuli/daily-brief-newspaper)"
SEC_USER_AGENT = "DailyBriefStockVerifier/1.0 github.com/kanuli/daily-brief-newspaper"
MAX_EVENT_AGE_HOURS = 36
MAX_ARTICLES_PER_RUN = 4

COMPANY = {
    "NVDA": "NVIDIA",
    "AAPL": "Apple",
    "TSM": "TSMC",
    "PLTR": "Palantir",
    "MSFT": "Microsoft",
    "GOOG": "Alphabet / Google",
    "EMXC": "iShares MSCI Emerging Markets ex China ETF",
    "EWY": "iShares MSCI South Korea ETF",
    "VT": "Vanguard Total World Stock ETF",
}

# Free first-party feeds.  Missing/unavailable feeds are a recoverable condition;
# the SEC and seed channels continue independently.
OFFICIAL_FEEDS = (
    ("AAPL", "Apple Developer", "https://developer.apple.com/news/rss/news.rss"),
    ("AAPL", "Apple Newsroom", "https://www.apple.com/newsroom/rss-feed.rss"),
    ("NVDA", "NVIDIA Newsroom", "https://nvidianews.nvidia.com/cats/press_release.xml"),
    ("MSFT", "Microsoft Official Blog", "https://blogs.microsoft.com/feed/"),
    ("GOOG", "Google Blog", "https://blog.google/rss/"),
)

# SEC CIKs for company equities. ETFs are intentionally excluded: issuer fund
# pages and holdings are a better primary source than routine trust filings.
SEC_CIK = {
    "NVDA": "0001045810",
    "AAPL": "0000320193",
    "TSM": "0001046179",
    "PLTR": "0001321655",
    "MSFT": "0000789019",
    "GOOG": "0001652044",
}
SEC_FORMS = {"8-K", "10-Q", "10-K", "6-K", "20-F"}

HIGH_SIGNAL_WITHOUT_CORROBORATION = {"earnings", "regulatory", "capital"}


@dataclass(frozen=True)
class PrimaryEvent:
    ticker: str
    event_type: str
    title: str
    url: str
    source: str
    published_at: datetime
    summary: str = ""
    event_id: str = ""
    secondary_sources: tuple[tuple[str, str], ...] = ()
    facts: dict[str, str] | None = None
    channel: str = "official-feed"


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def clean_html(value: str | None) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return normalize(text)


def http_get(url: str, *, sec: bool = False, timeout: int = 15) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT if sec else USER_AGENT,
            "Accept": "application/json, application/rss+xml, application/atom+xml, application/xml, text/xml, text/html, */*",
        },
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(1.0)
    raise RuntimeError(str(last_error))


def event_key(ticker: str, source: str, url: str, title: str) -> str:
    raw = f"{ticker}\n{source}\n{url}\n{title}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:18]


def existing_identity(stocks: dict[str, Any]) -> tuple[set[str], set[str]]:
    ids: set[str] = set()
    urls: set[str] = set()
    for block in (stocks.get("tickers") or {}).values():
        if not isinstance(block, dict):
            continue
        for story in block.get("stories") or []:
            if not isinstance(story, dict):
                continue
            if story.get("id"):
                ids.add(str(story["id"]))
            if story.get("sourceUrl"):
                urls.add(str(story["sourceUrl"]).strip())
            for source in story.get("sources") or []:
                if isinstance(source, dict) and source.get("url"):
                    urls.add(str(source["url"]).strip())
    return ids, urls


def load_staging_candidates(path: Path) -> list[dict[str, Any]]:
    data = load_json(path)
    desks = data.get("desks") if isinstance(data.get("desks"), dict) else {}
    items = desks.get("stock-news") if isinstance(desks.get("stock-news"), list) else []
    return [item for item in items if isinstance(item, dict)]


def parse_feed(payload: bytes, ticker: str, source: str, now: datetime) -> list[PrimaryEvent]:
    root = ET.fromstring(payload)
    events: list[PrimaryEvent] = []

    # RSS 2.0
    for item in root.findall(".//item")[:30]:
        title = clean_html(item.findtext("title"))
        link = normalize(item.findtext("link"))
        summary = clean_html(item.findtext("description"))
        published = parse_datetime(item.findtext("pubDate") or item.findtext("date"))
        if not title or not link or not published:
            continue
        event_type = classify_event(title, summary)
        if not event_type:
            continue
        if now - published > timedelta(hours=MAX_EVENT_AGE_HOURS) or published > now + timedelta(hours=1):
            continue
        events.append(PrimaryEvent(
            ticker=ticker,
            event_type=event_type,
            title=title,
            url=link,
            source=source,
            published_at=published,
            summary=summary[:700],
            event_id=event_key(ticker, source, link, title),
        ))

    # Atom feeds
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//a:entry", ns)[:30]:
        title = clean_html(entry.findtext("a:title", default="", namespaces=ns))
        link_node = entry.find("a:link[@rel='alternate']", ns) or entry.find("a:link", ns)
        link = normalize(link_node.get("href") if link_node is not None else "")
        summary = clean_html(
            entry.findtext("a:summary", default="", namespaces=ns)
            or entry.findtext("a:content", default="", namespaces=ns)
        )
        published = parse_datetime(
            entry.findtext("a:published", default="", namespaces=ns)
            or entry.findtext("a:updated", default="", namespaces=ns)
        )
        if not title or not link or not published:
            continue
        event_type = classify_event(title, summary)
        if not event_type:
            continue
        if now - published > timedelta(hours=MAX_EVENT_AGE_HOURS) or published > now + timedelta(hours=1):
            continue
        events.append(PrimaryEvent(
            ticker=ticker,
            event_type=event_type,
            title=title,
            url=link,
            source=source,
            published_at=published,
            summary=summary[:700],
            event_id=event_key(ticker, source, link, title),
        ))

    return events


def collect_official_feed_events(now: datetime, errors: list[str]) -> list[PrimaryEvent]:
    events: list[PrimaryEvent] = []
    for ticker, source, url in OFFICIAL_FEEDS:
        try:
            events.extend(parse_feed(http_get(url), ticker, source, now))
        except Exception as exc:
            errors.append(f"official-feed {ticker} {source}: {str(exc)[:180]}")
    return events


def sec_filing_url(cik: str, accession: str, primary_document: str) -> str:
    cik_num = str(int(cik))
    accession_compact = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{cik_num}/{accession_compact}/{primary_document}"


def collect_sec_events(now: datetime, errors: list[str]) -> list[PrimaryEvent]:
    events: list[PrimaryEvent] = []
    today_utc = now.date()
    for ticker, cik in SEC_CIK.items():
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        try:
            data = json.loads(http_get(url, sec=True).decode("utf-8"))
            recent = ((data.get("filings") or {}).get("recent") or {})
            forms = recent.get("form") or []
            filing_dates = recent.get("filingDate") or []
            accessions = recent.get("accessionNumber") or []
            documents = recent.get("primaryDocument") or []
            descriptions = recent.get("primaryDocDescription") or []
            for index, form in enumerate(forms[:40]):
                if form not in SEC_FORMS:
                    continue
                try:
                    filed = date.fromisoformat(str(filing_dates[index]))
                except Exception:
                    continue
                # SEC JSON supplies filing date rather than filing timestamp.
                # Two UTC calendar days is deliberately conservative around
                # after-hours filings and HKT midnight boundaries.
                if (today_utc - filed).days < 0 or (today_utc - filed).days > 1:
                    continue
                accession = str(accessions[index])
                primary = str(documents[index])
                direct = sec_filing_url(cik, accession, primary)
                description = normalize(descriptions[index] if index < len(descriptions) else "")
                published = datetime.combine(filed, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=16)
                title = f"{COMPANY[ticker]} {form} filing {filing_dates[index]}"
                events.append(PrimaryEvent(
                    ticker=ticker,
                    event_type="regulatory",
                    title=title,
                    url=direct,
                    source="U.S. SEC EDGAR",
                    published_at=min(published, now),
                    summary=description,
                    event_id=f"sec-{ticker.lower()}-{accession.lower()}",
                    facts={"form": form, "filingDate": str(filing_dates[index]), "accession": accession},
                    channel="sec",
                ))
        except Exception as exc:
            errors.append(f"sec {ticker}: {str(exc)[:180]}")
        time.sleep(0.12)  # respectful pacing for data.sec.gov
    return events


def collect_seed_events(now: datetime, errors: list[str]) -> list[PrimaryEvent]:
    data = load_json(SEEDS_PATH)
    output: list[PrimaryEvent] = []
    for seed in data.get("events") or []:
        if not isinstance(seed, dict):
            continue
        try:
            ticker = normalize(seed.get("ticker")).upper()
            if ticker not in TRACKED:
                continue
            expires = parse_datetime(seed.get("expiresAt"))
            announced = parse_datetime(seed.get("announcedAt")) or parse_datetime(seed.get("verifiedAt"))
            if not expires or not announced or now > expires:
                continue
            event_type = normalize(seed.get("eventType")) or classify_event(seed.get("officialTitle", ""))
            if not event_type:
                continue
            secondary = tuple(
                (normalize(item.get("name")), normalize(item.get("url")))
                for item in seed.get("secondarySources") or []
                if isinstance(item, dict) and item.get("name") and item.get("url")
            )
            output.append(PrimaryEvent(
                ticker=ticker,
                event_type=event_type,
                title=normalize(seed.get("officialTitle")),
                url=normalize(seed.get("officialUrl")),
                source=normalize(seed.get("officialSource")) or "Official source",
                published_at=announced,
                summary="",
                event_id=normalize(seed.get("id")) or event_key(ticker, "seed", seed.get("officialUrl", ""), seed.get("officialTitle", "")),
                secondary_sources=secondary,
                facts={str(k): normalize(v) for k, v in (seed.get("facts") or {}).items()},
                channel="editor-seed",
            ))
        except Exception as exc:
            errors.append(f"seed {seed.get('id')}: {str(exc)[:180]}")
    return output


def hkt_label(dt: datetime) -> str:
    local = dt.astimezone(HKT)
    return f"{local.month}月{local.day}日{local.hour:02d}:{local.minute:02d} HKT核實"


def build_seed_article(event: PrimaryEvent, verified_at: datetime) -> dict[str, Any] | None:
    if event.ticker == "AAPL" and event.event_id == "stock-aapl-apple-event-20260909":
        facts = event.facts or {}
        sources = [{"name": event.source, "url": event.url}] + [
            {"name": name, "url": url} for name, url in event.secondary_sources
        ]
        return {
            "id": event.event_id,
            "ticker": event.ticker,
            "desk": "stock-news",
            "storyType": "VERIFIED OFFICIAL / PRODUCT EVENT",
            "impact": "↔",
            "impactLabel": "PRODUCT CYCLE",
            "title": "Apple官方確定9月9日舉行特別活動，下一輪產品發布進入倒數",
            "dek": f"Apple第一手公告確認活動將於9月9日{facts.get('eventTime') or '10:00 PT'}舉行，Reuters亦獨立報道活動日期。",
            "summary": "Apple已正式公布9月9日特別活動，市場由傳聞階段轉入等待公司正式發布產品與規格。",
            "body": (
                f"Apple Developer於8月26日正式公布特別活動，日期為2026年9月9日，時間為{facts.get('eventTime') or '10:00 PT'}；"
                f"官方列出的觀看渠道包括{facts.get('watchChannels') or 'Apple官方平台'}。Reuters同日亦獨立確認活動日期，"
                "因此這項事件已通過Stock News的一手來源核實門檻。\n\n"
                "目前可以確認的是活動本身及時間；至於新iPhone型號、摺疊裝置或其他產品規格，在Apple正式公布前仍屬市場預期，"
                "本稿不把分析師或媒體推測寫成公司已確認事實。對AAPL而言，下一個可核實節點是活動當日的實際產品、價格、供應與上市安排。"
            ),
            "context": "Apple年度主要硬件發布通常會影響iPhone換機周期、產品組合、平均售價與供應鏈預期；但正式規格應以公司活動公布為準。",
            "why": "活動日期由Apple第一手來源確認，令產品周期由市場傳聞轉為有明確時間表的正式催化事件。",
            "watchNext": "留意9月9日Apple正式公布的產品、價格、預售／上市時間，以及管理層對供應與Apple Intelligence功能的說明。",
            "sourceName": event.source,
            "sourceUrl": event.url,
            "timeLabel": hkt_label(verified_at),
            "sources": sources,
            "verificationMode": "EDITOR_SEED_PRIMARY_PLUS_SECONDARY",
            "verifiedAt": verified_at.isoformat(),
        }
    return None


def event_label(event_type: str) -> tuple[str, str]:
    mapping = {
        "earnings": ("季度業績", "EARNINGS"),
        "guidance": ("業績指引", "GUIDANCE"),
        "product-event": ("產品／活動公告", "PRODUCT / EVENT"),
        "partnership": ("合作／投資公告", "PARTNERSHIP"),
        "regulatory": ("監管／正式披露", "REGULATORY"),
        "capital": ("資本安排", "CAPITAL"),
    }
    return mapping.get(event_type, ("公司公告", "OFFICIAL UPDATE"))


def build_official_article(event: PrimaryEvent, corroboration: dict | None, verified_at: datetime) -> dict[str, Any]:
    company = COMPANY[event.ticker]
    label_zh, label_en = event_label(event.event_type)
    source_title = event.title[:220]
    sources = [{"name": event.source, "url": event.url}]
    if corroboration and corroboration.get("url"):
        sources.append({"name": normalize(corroboration.get("source")) or "Independent source", "url": normalize(corroboration.get("url"))})

    return {
        "id": f"stock-{event.ticker.lower()}-{event.event_id}",
        "ticker": event.ticker,
        "desk": "stock-news",
        "storyType": f"VERIFIED OFFICIAL / {label_en}",
        "impact": "↔",
        "impactLabel": "OFFICIAL DISCLOSURE",
        "title": f"{company}發布最新{label_zh}，第一手資料已通過Stock News核實",
        "dek": f"{event.source}發布「{source_title}」；自動核實器只在官方／監管來源出現後才升格為已核實新聞。",
        "summary": f"{company}已透過{event.source}發布新的{label_zh}，事件由第一手來源確認；市場傳聞或預測不會被當成正式公告。",
        "body": (
            f"{company}透過{event.source}發布新公告，官方標題為「{source_title}」。"
            f"這項內容由公司／監管第一手來源直接確認，發布時間為{event.published_at.astimezone(HKT).strftime('%Y年%m月%d日 %H:%M HKT')}。"
            "Stock News的自動核實器不會因搜尋結果、社交平台貼文或預測文章出現相似標題，就把未正式發布的消息當作公司事實。\n\n"
            f"對{event.ticker}而言，這項{label_zh}提供了新的正式資訊節點。"
            "本自動稿只陳述第一手來源能確認的事件存在，不會自行補上未從官方文件讀出的財務數字、產品規格或股價方向；"
            "如有更完整的人工編輯核實稿，其內容可在後續版本取代這個速報。"
        ),
        "context": f"{company}屬Stock News固定追蹤標的；官方公告、投資者關係資料與監管文件是自動核實流程的最高優先證據。",
        "why": "第一手公告可把市場傳聞與已確認事實清楚分開，並為後續財務、產品或監管分析提供可靠時間點。",
        "watchNext": "留意官方文件的完整細節、管理層後續說明，以及是否有新的監管文件或可信獨立媒體交叉核實。",
        "sourceName": event.source,
        "sourceUrl": event.url,
        "timeLabel": hkt_label(verified_at),
        "sources": sources,
        "verificationMode": "PRIMARY_SOURCE_AUTO",
        "verifiedAt": verified_at.isoformat(),
        "primaryPublishedAt": event.published_at.isoformat(),
    }


def build_sec_article(event: PrimaryEvent, verified_at: datetime) -> dict[str, Any]:
    company = COMPANY[event.ticker]
    facts = event.facts or {}
    form = facts.get("form") or "SEC filing"
    filing_date = facts.get("filingDate") or event.published_at.date().isoformat()
    return {
        "id": f"stock-{event.event_id}",
        "ticker": event.ticker,
        "desk": "stock-news",
        "storyType": f"VERIFIED OFFICIAL / SEC {form}",
        "impact": "↔",
        "impactLabel": "REGULATORY FILING",
        "title": f"{company}提交最新{form}文件，正式監管披露已更新",
        "dek": f"SEC EDGAR顯示{company}於{filing_date}提交{form}；Stock News直接連結第一手監管文件。",
        "summary": f"{company}出現新的{form}監管文件，已由SEC EDGAR第一手資料確認，不依賴市場轉述。",
        "body": (
            f"美國證券交易委員會SEC的EDGAR公司提交紀錄顯示，{company}於{filing_date}提交{form}文件。"
            "Stock News直接使用SEC原始文件作為核實來源，因此不需要等待新聞網站轉載才確認『已提交文件』這項事實。\n\n"
            f"{form}可能涵蓋業績、重大公司事項或其他法定披露，但不同文件內容差異可以很大。"
            "這個自動速報不會只憑表格類型推斷具體財務影響；讀者應以連結內的正式文件內容為準，後續若有具體數字或重大事項通過完整編輯核實，會再更新成較深入稿件。"
        ),
        "context": "SEC文件是美國上市公司最重要的正式披露渠道之一；10-Q、10-K、8-K以及外國發行人的6-K／20-F均可能包含市場重要資訊。",
        "why": "監管文件提供可稽核的第一手時間戳與正式披露，能避免把提前刊出的預測頁或市場傳聞錯當成公司結果。",
        "watchNext": "閱讀SEC原始文件的具體披露內容，並留意公司投資者關係網站、管理層電話會議及可信媒體對重大事項的後續核實。",
        "sourceName": "U.S. SEC EDGAR",
        "sourceUrl": event.url,
        "timeLabel": hkt_label(verified_at),
        "sources": [{"name": "U.S. SEC EDGAR", "url": event.url}],
        "verificationMode": "SEC_PRIMARY_AUTO",
        "verifiedAt": verified_at.isoformat(),
        "primaryPublishedAt": event.published_at.isoformat(),
    }


def select_articles(
    events: list[PrimaryEvent],
    candidates: list[dict[str, Any]],
    stocks: dict[str, Any],
    now: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    existing_ids, existing_urls = existing_identity(stocks)
    selected: list[dict[str, Any]] = []
    audit: list[dict[str, str]] = []
    ticker_used: set[str] = set()

    # Seed > SEC > official feed, then newest within each channel.
    channel_rank = {"editor-seed": 0, "sec": 1, "official-feed": 2}
    events.sort(key=lambda event: (channel_rank.get(event.channel, 9), -event.published_at.timestamp()))

    for event in events:
        if len(selected) >= MAX_ARTICLES_PER_RUN:
            break
        if event.ticker in ticker_used:
            continue
        article_id = event.event_id if event.channel == "editor-seed" else (
            f"stock-{event.event_id}" if event.channel == "sec" else f"stock-{event.ticker.lower()}-{event.event_id}"
        )
        if article_id in existing_ids or event.url in existing_urls:
            audit.append({"ticker": event.ticker, "event": event.title, "decision": "duplicate"})
            continue

        if event.channel == "editor-seed":
            article = build_seed_article(event, now)
            if not article:
                audit.append({"ticker": event.ticker, "event": event.title, "decision": "unsupported-seed"})
                continue
            selected.append(article)
            ticker_used.add(event.ticker)
            audit.append({"ticker": event.ticker, "event": event.title, "decision": "verified-editor-seed"})
            continue

        if event.channel == "sec":
            selected.append(build_sec_article(event, now))
            ticker_used.add(event.ticker)
            audit.append({"ticker": event.ticker, "event": event.title, "decision": "verified-sec-primary"})
            continue

        corroboration = best_corroboration(event.ticker, f"{event.title} {event.summary}", candidates)
        # Earnings/regulatory/capital disclosures are authoritative in the
        # primary source itself. Other company announcements require trusted
        # discovery corroboration before automatic publication.
        if event.event_type not in HIGH_SIGNAL_WITHOUT_CORROBORATION and not corroboration:
            audit.append({"ticker": event.ticker, "event": event.title, "decision": "primary-found-await-corroboration"})
            continue

        selected.append(build_official_article(event, corroboration, now))
        ticker_used.add(event.ticker)
        audit.append({"ticker": event.ticker, "event": event.title, "decision": "verified-primary"})

    return selected, audit


def write_draft(path: Path, articles: list[dict[str, Any]], audit: list[dict[str, str]], errors: list[str], now: datetime) -> None:
    draft_id = "stock-auto-" + now.astimezone(HKT).strftime("%Y%m%d-%H%M%S-hkt")
    payload = {
        "version": 1,
        "status": "VERIFIED_DRAFT",
        "draftId": draft_id,
        "createdAt": now.isoformat(),
        "targetPublication": now.astimezone(HKT).replace(minute=0, second=0, microsecond=0).isoformat(),
        "publicationType": "STOCK_NEWS",
        "verificationMode": "PRIMARY_SOURCE_RULES_V1",
        "articles": articles,
        "audit": audit[:80],
        "errors": errors[:40],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("staging", type=Path, help="rolling search-staging.json")
    parser.add_argument("--output", type=Path, default=Path("/tmp/stock-prepublish.json"))
    parser.add_argument("--official-events-fixture", type=Path, default=None,
                        help="test-only JSON array/object of normalized primary events; disables network primary-source fetches")
    parser.add_argument("--now", default=None, help="test-only timezone-aware ISO current time")
    args = parser.parse_args()

    now = parse_datetime(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        raise SystemExit("--now must be timezone-aware ISO")
    stocks = load_json(STOCKS_PATH)
    candidates = load_staging_candidates(args.staging)
    errors: list[str] = []

    events = collect_seed_events(now, errors)
    if args.official_events_fixture:
        fixture = load_json(args.official_events_fixture)
        raw_events = fixture.get("events") if isinstance(fixture.get("events"), list) else []
        for raw in raw_events:
            if not isinstance(raw, dict):
                continue
            published = parse_datetime(raw.get("publishedAt"))
            ticker = normalize(raw.get("ticker")).upper()
            if not published or ticker not in TRACKED:
                continue
            events.append(PrimaryEvent(
                ticker=ticker,
                event_type=normalize(raw.get("eventType")) or "regulatory",
                title=normalize(raw.get("title")),
                url=normalize(raw.get("url")),
                source=normalize(raw.get("source")) or "Fixture Official",
                published_at=published,
                summary=normalize(raw.get("summary")),
                event_id=normalize(raw.get("eventId")) or event_key(ticker, raw.get("source", ""), raw.get("url", ""), raw.get("title", "")),
                channel=normalize(raw.get("channel")) or "official-feed",
                facts={str(k): normalize(v) for k, v in (raw.get("facts") or {}).items()},
            ))
    else:
        events.extend(collect_official_feed_events(now, errors))
        events.extend(collect_sec_events(now, errors))

    articles, audit = select_articles(events, candidates, stocks, now)
    write_draft(args.output, articles, audit, errors, now)

    print(
        "STOCK_VERIFIED_PRODUCER_PASS",
        f"primary_events={len(events)}",
        f"staging_candidates={len(candidates)}",
        f"verified_articles={len(articles)}",
        f"errors={len(errors)}",
        f"output={args.output}",
    )
    for row in audit[:20]:
        print(" ", row.get("ticker"), row.get("decision"), row.get("event", "")[:120])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
