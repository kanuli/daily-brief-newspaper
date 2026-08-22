#!/usr/bin/env python3
"""Free rolling news discovery collector for Daily Brief.

This script is intentionally a discovery/staging layer, not a publisher.
It collects recent candidate headlines for all public desks every 15 minutes,
deduplicates them, and writes data/search-staging.json. The hourly publisher
must independently verify, rank, rewrite and source-check candidates before
publishing them.
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
USER_AGENT = "DailyBriefRollingCollector/1.0 (+https://github.com/kanuli/daily-brief-newspaper)"
RETENTION_HOURS = 8
MAX_PER_DESK = 100
GOOGLE_MIN_BEFORE_FALLBACK = 4

QUERY_PLAN: dict[str, list[str]] = {
    "world": [
        "world news Europe Africa Americas Oceania latest when:2h",
        "breaking international politics court disaster public safety latest when:2h",
    ],
    "asia": [
        "Asia news East Southeast South Central West Asia Middle East latest when:2h",
        "Asia politics society disaster diplomacy security economy latest when:2h",
    ],
    "hong-kong": [
        "Hong Kong news society court transport housing health education latest when:2h",
        "香港 新聞 社會 法庭 交通 房屋 醫療 教育 最新 when:2h",
    ],
    "japan": [
        "Japan news society politics court transport weather culture technology latest when:2h",
        "日本 ニュース 社会 政治 事件 交通 天気 文化 最新 when:2h",
    ],
    "finance": [
        "global markets economy central bank rates stocks bonds currency oil latest when:2h",
        "US Europe Asia market economy companies finance latest when:2h",
    ],
    "stock-news": [
        "NVDA AAPL TSM PLTR MSFT GOOG stock company news latest when:2h",
        "EMXC EWY VT ETF market holdings flows latest when:2h",
    ],
    "ai-tech": [
        "AI technology semiconductor cloud cybersecurity software regulation latest when:2h",
        "artificial intelligence chips consumer tech research latest when:2h",
    ],
    "manga-anime": [
        "anime manga industry production release delay publisher voice actor latest when:6h",
        "アニメ 漫画 最新 ニュース 制作 放送 出版 when:6h",
    ],
    "manchester-united": [
        "Manchester United latest news transfer injury match training club when:2h",
        "Manchester United official news latest when:6h",
    ],
    "football": [
        "football soccer latest news Premier League EFL La Liga Serie A Bundesliga Ligue 1 when:2h",
        "football transfer injury suspension manager club latest when:2h",
        "UEFA Champions League Europa Conference international football latest when:2h",
        "J League Japan football Hong Kong football HKPL AFC latest when:2h",
    ],
}

LOCALES = {
    "hong-kong": ("zh-HK", "HK", "HK:zh-Hant"),
    "japan": ("ja", "JP", "JP:ja"),
    "manga-anime": ("ja", "JP", "JP:ja"),
}


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
        source_node = item.find("source")
        source = clean_text(source_node.text if source_node is not None else "")
        if not source:
            source = clean_text(item.findtext("author")) or provider
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


def retained_candidates(existing: dict[str, Any], cutoff: datetime) -> dict[str, dict[str, dict[str, Any]]]:
    desks: dict[str, dict[str, dict[str, Any]]] = {desk: {} for desk in QUERY_PLAN}
    old_desks = existing.get("desks") if isinstance(existing.get("desks"), dict) else {}
    for desk in QUERY_PLAN:
        for item in old_desks.get(desk, []) if isinstance(old_desks.get(desk), list) else []:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            seen = parse_date(str(item.get("lastSeenAt") or item.get("firstSeenAt") or ""))
            if seen and seen >= cutoff:
                desks[desk][str(item["id"])] = item
    return desks


def collect(existing: dict[str, Any]) -> dict[str, Any]:
    started = now_utc()
    cutoff = started - timedelta(hours=RETENTION_HOURS)
    merged = retained_candidates(existing, cutoff)
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
            key=lambda x: parse_date(str(x.get("publishedAt") or x.get("lastSeenAt") or "")) or datetime.min.replace(tzinfo=timezone.utc),
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
