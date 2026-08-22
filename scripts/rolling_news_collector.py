#!/usr/bin/env python3
"""Free rolling news discovery collector for Daily Brief.

This is a discovery/staging layer, not a publisher. It collects recent
candidate headlines for all public desks every 15 minutes, deduplicates them,
and writes data/search-staging.json. Hourly publishers must independently
verify, rank, rewrite and source-check candidates before publication.
"""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HKT = timezone(timedelta(hours=8))
USER_AGENT = "DailyBriefRollingCollector/1.3 (+https://github.com/kanuli/daily-brief-newspaper)"
RETENTION_HOURS = 8
MAX_PER_DESK = 60
GOOGLE_MIN_BEFORE_FALLBACK = 4

FRESHNESS_HOURS = {
    "world": 8,
    "asia": 8,
    "hong-kong": 8,
    "japan": 8,
    "finance": 8,
    "stock-news": 8,
    "ai-tech": 8,
    "manga-anime": 48,
    "manchester-united": 12,
    "football": 12,
}

QUERY_PLAN: dict[str, list[str]] = {
    "world": [
        '(Europe OR Africa OR "North America" OR "South America" OR Oceania) when:4h',
        'international breaking politics court disaster public safety when:4h',
    ],
    "asia": [
        '(Asia OR China OR Korea OR India OR ASEAN OR "Middle East" OR "Central Asia") when:4h',
        'Asia politics society disaster diplomacy economy technology when:4h',
    ],
    "hong-kong": [
        '"Hong Kong" when:4h',
        '香港 when:4h',
    ],
    "japan": [
        'Japan when:4h',
        '日本 when:4h',
    ],
    "finance": [
        '(markets OR economy OR "central bank" OR rates OR bonds OR currency OR oil) when:4h',
        '(Wall Street OR Europe markets OR Asia markets OR companies finance) when:4h',
    ],
    "stock-news": [
        '(NVDA OR Nvidia OR AAPL OR Apple OR TSM OR TSMC OR PLTR OR Palantir OR MSFT OR Microsoft OR GOOG OR Alphabet) when:4h',
        '(EMXC OR EWY OR VT) ETF when:8h',
    ],
    "ai-tech": [
        '(AI OR "artificial intelligence" OR semiconductor OR cloud OR cybersecurity) when:4h',
        '(technology OR software OR chips OR consumer tech OR tech regulation) when:4h',
    ],
    "manga-anime": [
        'anime when:48h',
        'manga when:48h',
        'アニメ when:48h',
        '漫画 when:48h',
    ],
    "manchester-united": [
        '"Manchester United" when:6h',
        '"Man Utd" transfer injury match club when:12h',
    ],
    "football": [
        '(football OR soccer) (Premier League OR EFL OR "La Liga" OR "Serie A" OR Bundesliga OR "Ligue 1") when:4h',
        'football transfer injury suspension manager club when:4h',
        '(UEFA OR "Champions League" OR "Europa League" OR international football) when:6h',
        '("J League" OR J-League OR "Hong Kong Premier League" OR HKFA OR "AFC Champions League") when:8h',
    ],
}

LOCALES = {
    "hong-kong": ("zh-HK", "HK", "HK:zh-Hant"),
    "japan": ("ja", "JP", "JP:ja"),
    "manga-anime": ("ja", "JP", "JP:ja"),
}

FOOTBALL_FALSE_POSITIVE = re.compile(
    r"\b(?:NFL|NCAA|MLB|NBA|WNBA|quarterback|touchdown|super bowl|pro bowl|baseball|formula\s*1|\bF1\b)\b|\bAFC\s+(?:East|West|North|South)\b",
    re.I,
)

FOOTBALL_POSITIVE = re.compile(
    r"football|soccer|premier league|\bEFL\b|la liga|serie a|bundesliga|ligue 1|"
    r"\bUEFA\b|\bFIFA\b|champions league|europa league|conference league|j[- ]?league|"
    r"hong kong premier league|\bHKPL\b|\bHKFA\b|afc champions league|"
    r"arsenal|chelsea|liverpool|tottenham|manchester united|man utd|man united|manchester city|"
    r"newcastle|aston villa|everton|brighton|west ham|fulham|brentford|hull city|wrexham|watford|"
    r"sunderland|ipswich|afc wimbledon|barcelona|real madrid|atletico|juventus|inter milan|ac milan|"
    r"bayern|dortmund|paris saint-germain|\bpsg\b|marseille|portland thorns|"
    r"transfer|striker|midfielder|defender|goalkeeper|manager|fixture|lineup|team news|goal\.com|transfermarkt",
    re.I,
)

STOCK_TERMS = (
    "nvda", "nvidia", "aapl", "apple", "tsm", "tsmc", "taiwan semiconductor",
    "pltr", "palantir", "msft", "microsoft", "goog", "google", "alphabet",
    "emxc", "ewy", " vt ", "vanguard total world", "emerging markets ex china",
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def clean_text(value: str | None) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", value).strip()


def normalize_title(title: str) -> str:
    text = clean_text(title).lower()
    text = re.sub(r"\s+-\s+[^-]{2,80}$", "", text)
    return re.sub(r"[^a-z0-9\u3400-\u9fff\u3040-\u30ff]+", " ", text).strip()


def candidate_id(desk: str, title: str) -> str:
    raw = f"{desk}\n{normalize_title(title)}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()[:20]


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def candidate_is_fresh(desk: str, pub: datetime | None, discovered: datetime) -> bool:
    if pub is None:
        return True
    max_age = timedelta(hours=FRESHNESS_HOURS[desk])
    return discovered - max_age <= pub <= discovered + timedelta(hours=1)


def candidate_is_relevant(desk: str, title: str, source: str) -> bool:
    combined = f" {title} {source} "
    lowered = combined.lower()
    if desk == "football":
        if FOOTBALL_FALSE_POSITIVE.search(combined):
            return False
        return bool(FOOTBALL_POSITIVE.search(combined))
    if desk == "manchester-united":
        return (
            "manchester united" in lowered
            or "man utd" in lowered
            or "man united" in lowered
            or "manchester united website" in lowered
        )
    if desk == "stock-news":
        return any(term in lowered for term in STOCK_TERMS)
    return True


def http_get(url: str, timeout: int = 15) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
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
                time.sleep(1.5)
    raise RuntimeError(str(last_error))


def google_url(query: str, desk: str) -> str:
    hl, gl, ceid = LOCALES.get(desk, ("en-US", "US", "US:en"))
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": query, "hl": hl, "gl": gl, "ceid": ceid}
    )


def bing_url(query: str) -> str:
    query = re.sub(r"\s+when:\d+[hm]", "", query, flags=re.I)
    return "https://www.bing.com/news/search?" + urllib.parse.urlencode(
        {"q": query, "format": "rss"}
    )


def rss_items(payload: bytes, provider: str, desk: str, query: str, discovered: datetime) -> list[dict[str, Any]]:
    root = ET.fromstring(payload)
    out: list[dict[str, Any]] = []
    for item in root.findall(".//item")[:30]:
        title = clean_text(item.findtext("title"))
        link = clean_text(item.findtext("link"))
        if not title or not link:
            continue
        pub = parse_date(item.findtext("pubDate"))
        if not candidate_is_fresh(desk, pub, discovered):
            continue
        source_node = item.find("source")
        source = clean_text(source_node.text if source_node is not None else "")
        if not source:
            source = clean_text(item.findtext("author")) or provider
        if not candidate_is_relevant(desk, title, source):
            continue
        cid = candidate_id(desk, title)
        out.append(
            {
                "id": cid,
                "desk": desk,
                "title": title,
                "url": link,
                "source": source,
                "provider": provider,
                "query": query,
                "publishedAt": iso(pub) if pub else None,
                "firstSeenAt": iso(discovered),
                "lastSeenAt": iso(discovered),
            }
        )
    return out


def load_existing(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def retained_candidates(existing: dict[str, Any], now: datetime) -> dict[str, dict[str, dict[str, Any]]]:
    seen_cutoff = now - timedelta(hours=RETENTION_HOURS)
    desks: dict[str, dict[str, dict[str, Any]]] = {desk: {} for desk in QUERY_PLAN}
    old_desks = existing.get("desks") if isinstance(existing.get("desks"), dict) else {}
    for desk in QUERY_PLAN:
        for item in old_desks.get(desk, []) if isinstance(old_desks.get(desk), list) else []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            title = str(item.get("title") or "")
            source = str(item.get("source") or "")
            if not candidate_is_relevant(desk, title, source):
                continue
            seen = parse_date(str(item.get("lastSeenAt") or item.get("firstSeenAt") or ""))
            pub = parse_date(str(item.get("publishedAt") or ""))
            if not seen or seen < seen_cutoff:
                continue
            if pub and not candidate_is_fresh(desk, pub, now):
                continue
            desks[desk][str(item["id"])] = item
    return desks


def collect(existing: dict[str, Any]) -> dict[str, Any]:
    started = now_utc()
    merged = retained_candidates(existing, started)
    errors: list[dict[str, str]] = []
    query_audit: dict[str, dict[str, int]] = {}

    for desk, queries in QUERY_PLAN.items():
        discovered_this_run: set[str] = set()
        query_audit[desk] = {"queries": len(queries), "googleItems": 0, "bingFallbackItems": 0}
        for query in queries:
            try:
                items = rss_items(http_get(google_url(query, desk)), "Google News RSS", desk, query, started)
                query_audit[desk]["googleItems"] += len(items)
                for item in items:
                    discovered_this_run.add(item["id"])
                    old = merged[desk].get(item["id"])
                    if old:
                        item["firstSeenAt"] = old.get("firstSeenAt") or item["firstSeenAt"]
                    merged[desk][item["id"]] = item
            except Exception as exc:
                errors.append({"desk": desk, "provider": "Google News RSS", "query": query, "error": str(exc)[:240]})

        if len(discovered_this_run) < GOOGLE_MIN_BEFORE_FALLBACK:
            fallback_query = queries[0]
            try:
                items = rss_items(http_get(bing_url(fallback_query)), "Bing News RSS", desk, fallback_query, started)
                query_audit[desk]["bingFallbackItems"] += len(items)
                for item in items:
                    old = merged[desk].get(item["id"])
                    if old:
                        item["firstSeenAt"] = old.get("firstSeenAt") or item["firstSeenAt"]
                    merged[desk][item["id"]] = item
            except Exception as exc:
                errors.append({"desk": desk, "provider": "Bing News RSS", "query": fallback_query, "error": str(exc)[:240]})

    desks_out: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    for desk, by_id in merged.items():
        items = list(by_id.values())
        items.sort(
            key=lambda x: parse_date(str(x.get("publishedAt") or x.get("lastSeenAt") or ""))
            or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        items = items[:MAX_PER_DESK]
        desks_out[desk] = items
        counts[desk] = len(items)

    finished = now_utc()
    return {
        "version": 1,
        "mode": "ROLLING_NEWS_DISCOVERY_STAGING",
        "discoveryOnly": True,
        "verificationRequiredBeforePublish": True,
        "searchCadenceMinutes": 15,
        "publishCadenceMinutes": 60,
        "publishWindowHKT": "06:00-24:00",
        "publishSkipHKT": ["08:00"],
        "lastSearchStartedAt": iso(started),
        "lastSearchAt": iso(finished),
        "retentionHours": RETENTION_HOURS,
        "desks": desks_out,
        "candidateCounts": counts,
        "queryAudit": query_audit,
        "errors": errors[:100],
        "notes": [
            "Staging is discovery only; candidates are not published without independent verification.",
            "Football is researched as the full worldwide football news desk; results are one normal candidate type among transfers, injuries, fixtures, club, league and international developments.",
            "Football staging requires positive football relevance and filters American-football/baseball/F1 noise; Manchester United and Stock News use desk-specific relevance filters.",
            "Candidates with an explicit publication time older than the desk freshness limit are discarded before staging.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--existing", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=Path("data/search-staging.json"))
    args = parser.parse_args()

    existing = load_existing(args.existing)
    data = collect(existing)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total = sum(data["candidateCounts"].values())
    print(f"ROLLING_NEWS_SEARCH_PASS total_candidates={total} errors={len(data['errors'])}")
    for desk, count in data["candidateCounts"].items():
        print(f"  {desk}: {count}")
    return 0 if total > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
