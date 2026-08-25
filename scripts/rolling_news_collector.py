#!/usr/bin/env python3
"""Free rolling news discovery collector for Daily Brief.

This is a discovery/staging layer, not a publisher. It collects recent
candidate headlines for all public desks every 15 minutes, deduplicates them,
and writes data/search-staging.json. Hourly publishers must independently
verify, rank, rewrite and source-check candidates before publication.

The collector is deliberately broad. A small Live/headline edition must never
become a collection cap: staging should maintain a deep, diverse candidate
reservoir for every Cantonese topic desk.
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
USER_AGENT = "DailyBriefRollingCollector/1.4 (+https://github.com/kanuli/daily-brief-newspaper)"
RETENTION_HOURS = 24
MAX_PER_DESK = 120

# These are discovery-pool floors, never publication targets or caps. If the
# primary provider returns fewer unique candidates than the floor, broaden via
# free fallback discovery queries for that desk.
MIN_DISCOVERY_PER_DESK = {
    "world": 24,
    "asia": 24,
    "hong-kong": 16,
    "japan": 20,
    "finance": 20,
    "stock-news": 12,
    "ai-tech": 20,
    "manga-anime": 12,
    "manchester-united": 10,
    "football": 24,
}

FRESHNESS_HOURS = {
    "world": 24,
    "asia": 24,
    "hong-kong": 24,
    "japan": 24,
    "finance": 24,
    "stock-news": 24,
    "ai-tech": 24,
    "manga-anime": 72,
    "manchester-united": 48,
    "football": 48,
}

QUERY_PLAN: dict[str, list[str]] = {
    "world": [
        'Europe politics economy society court disaster security when:6h',
        'Africa politics economy society conflict disaster health when:8h',
        '(Canada OR Mexico OR "North America") politics economy society court disaster when:6h',
        '("South America" OR "Latin America") politics economy society election disaster when:8h',
        '(Australia OR "New Zealand" OR Oceania) politics economy society disaster when:8h',
        'international diplomacy conflict climate science public safety when:6h',
    ],
    "asia": [
        '(China OR Taiwan OR Korea OR Japan) politics economy society diplomacy when:6h',
        '(ASEAN OR Singapore OR Malaysia OR Thailand OR Vietnam OR Indonesia OR Philippines) when:6h',
        '(India OR Pakistan OR Bangladesh OR Sri Lanka OR Nepal) politics economy society when:6h',
        '("Middle East" OR Iran OR Israel OR Gaza OR Gulf OR Saudi OR UAE OR Iraq OR Syria OR Lebanon) when:6h',
        '("Central Asia" OR Kazakhstan OR Uzbekistan OR Caucasus OR Armenia OR Azerbaijan OR Georgia) when:12h',
        'Asia technology health disaster climate security when:6h',
    ],
    "hong-kong": [
        '香港 新聞 when:6h',
        '香港 政府 政策 立法會 法院 警方 when:8h',
        '香港 交通 房屋 醫療 教育 勞工 when:8h',
        '香港 經濟 社會 文化 環境 意外 when:8h',
        '"Hong Kong" politics court transport housing health education society when:8h',
    ],
    "japan": [
        '日本 ニュース when:6h',
        '日本 政治 国会 政府 外交 when:8h',
        '日本 社会 事件 裁判 犯罪 when:8h',
        '日本 地震 台風 天気 災害 交通 when:8h',
        '日本 経済 企業 産業 技術 AI when:8h',
        '日本 医療 教育 人口 労働 when:12h',
        '日本 文化 観光 生活 when:12h',
    ],
    "finance": [
        '(markets OR stocks OR bonds OR currency OR oil OR gold) when:6h',
        '(economy OR inflation OR jobs OR GDP OR trade) when:8h',
        '(Federal Reserve OR ECB OR BOJ OR PBOC OR "central bank") when:8h',
        '(Wall Street OR Europe markets OR Asia markets) when:6h',
        '(earnings OR guidance OR merger OR acquisition OR IPO) companies when:8h',
        '(Treasury yields OR dollar OR yen OR euro OR commodities) when:6h',
    ],
    "stock-news": [
        '(NVDA OR Nvidia OR AAPL OR Apple OR TSM OR TSMC) earnings guidance product analyst SEC when:8h',
        '(PLTR OR Palantir OR MSFT OR Microsoft OR GOOG OR Google OR Alphabet) earnings guidance product analyst SEC when:8h',
        '(EMXC OR EWY OR VT) ETF market flows holdings when:12h',
        '(NVDA OR AAPL OR TSM OR PLTR OR MSFT OR GOOG OR EMXC OR EWY OR VT) when:12h',
    ],
    "ai-tech": [
        '(AI OR "artificial intelligence" OR generative AI OR model) when:6h',
        '(semiconductor OR chip OR GPU OR foundry) when:6h',
        '(cloud OR software OR app OR enterprise technology) when:8h',
        '(cybersecurity OR data breach OR ransomware) when:8h',
        '(technology regulation OR AI regulation OR antitrust technology) when:8h',
        '(consumer tech OR smartphone OR computer OR robotics OR quantum) when:8h',
    ],
    "manga-anime": [
        'アニメ 新作 放送 延期 制作 when:72h',
        '漫画 出版 連載 休載 when:72h',
        'anime film box office studio streaming when:72h',
        'manga publisher creator serialization when:72h',
        '声優 アニメ 映画 イベント when:72h',
    ],
    "manchester-united": [
        '"Manchester United" when:12h',
        '"Manchester United" transfer injury contract when:24h',
        '"Manchester United" match fixture manager training when:24h',
        '"Man Utd" player team news when:24h',
    ],
    "football": [
        '(Premier League OR EFL OR Championship) football when:6h',
        '("La Liga" OR "Serie A" OR Bundesliga OR "Ligue 1") football when:8h',
        '(UEFA OR "Champions League" OR "Europa League" OR "Conference League") football when:8h',
        '(FIFA OR international football OR national team) match qualifier tournament when:8h',
        'football transfer injury suspension manager contract when:6h',
        '("J League" OR J-League OR J1 OR J2) football when:12h',
        '("Hong Kong Premier League" OR HKFA OR 港超 OR 香港足球) when:12h',
        '("AFC Champions League" OR AFC football OR Asian football) when:12h',
        'women football soccer league international when:12h',
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
    r"football|soccer|premier league|\bEFL\b|championship|la liga|serie a|bundesliga|ligue 1|"
    r"\bUEFA\b|\bFIFA\b|champions league|europa league|conference league|j[- ]?league|\bJ1\b|\bJ2\b|"
    r"hong kong premier league|\bHKPL\b|\bHKFA\b|港超|香港足球|afc champions league|"
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
    for item in root.findall(".//item")[:40]:
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


def merge_items(
    desk: str,
    items: list[dict[str, Any]],
    merged: dict[str, dict[str, dict[str, Any]]],
    discovered_this_run: set[str],
) -> None:
    for item in items:
        discovered_this_run.add(item["id"])
        old = merged[desk].get(item["id"])
        if old:
            item["firstSeenAt"] = old.get("firstSeenAt") or item["firstSeenAt"]
        merged[desk][item["id"]] = item


def collect(existing: dict[str, Any]) -> dict[str, Any]:
    started = now_utc()
    merged = retained_candidates(existing, started)
    errors: list[dict[str, str]] = []
    query_audit: dict[str, dict[str, int]] = {}

    for desk, queries in QUERY_PLAN.items():
        discovered_this_run: set[str] = set()
        floor = MIN_DISCOVERY_PER_DESK[desk]
        query_audit[desk] = {
            "queries": len(queries),
            "googleItems": 0,
            "bingFallbackQueries": 0,
            "bingFallbackItems": 0,
            "discoveryFloor": floor,
        }

        for query in queries:
            try:
                items = rss_items(http_get(google_url(query, desk)), "Google News RSS", desk, query, started)
                query_audit[desk]["googleItems"] += len(items)
                merge_items(desk, items, merged, discovered_this_run)
            except Exception as exc:
                errors.append({"desk": desk, "provider": "Google News RSS", "query": query, "error": str(exc)[:240]})

        # If the primary provider leaves a desk shallow, broaden across multiple
        # fallback queries rather than trying only one generic query. Stop once
        # the per-desk discovery floor is reached.
        if len(discovered_this_run) < floor:
            for query in queries:
                if len(discovered_this_run) >= floor:
                    break
                try:
                    items = rss_items(http_get(bing_url(query)), "Bing News RSS", desk, query, started)
                    query_audit[desk]["bingFallbackQueries"] += 1
                    query_audit[desk]["bingFallbackItems"] += len(items)
                    merge_items(desk, items, merged, discovered_this_run)
                except Exception as exc:
                    errors.append({"desk": desk, "provider": "Bing News RSS", "query": query, "error": str(exc)[:240]})

        query_audit[desk]["uniqueDiscoveredThisRun"] = len(discovered_this_run)
        query_audit[desk]["floorMetThisRun"] = int(len(discovered_this_run) >= floor)

    desks_out: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    underfilled: dict[str, dict[str, int]] = {}
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
        floor = MIN_DISCOVERY_PER_DESK[desk]
        if len(items) < floor:
            underfilled[desk] = {"count": len(items), "floor": floor}

    finished = now_utc()
    return {
        "version": 2,
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
        "maxCandidatesPerDesk": MAX_PER_DESK,
        "discoveryFloors": MIN_DISCOVERY_PER_DESK,
        "desks": desks_out,
        "candidateCounts": counts,
        "underfilledDesks": underfilled,
        "queryAudit": query_audit,
        "errors": errors[:100],
        "notes": [
            "Staging is discovery only; candidates are not published without independent verification.",
            "Discovery floors are breadth-health thresholds, never publication quotas or caps.",
            "All ten Cantonese desks use multi-angle queries; shallow primary discovery triggers multiple free fallback queries until the desk floor is reached or queries are exhausted.",
            "A short Live edition or homepage topFive must never reduce the depth of collection staging or public topic desks.",
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
    print(
        f"ROLLING_NEWS_SEARCH_PASS total_candidates={total} "
        f"underfilled_desks={len(data['underfilledDesks'])} errors={len(data['errors'])}"
    )
    for desk, count in data["candidateCounts"].items():
        floor = data["discoveryFloors"][desk]
        print(f"  {desk}: {count} (floor={floor})")
    return 0 if total > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
