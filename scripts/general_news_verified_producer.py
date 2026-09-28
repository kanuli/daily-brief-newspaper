#!/usr/bin/env python3
"""Create a source-constrained general-news VERIFIED_DRAFT.

The rolling collector is discovery only. This producer closes the missing
middle without inventing facts: it selects same-day candidates from named
publishers, limits public copy to facts present in the source headline, and
records the original candidate metadata for auditability.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HKT = timezone(timedelta(hours=8))
DESK_LABELS = {
    "world": "世界", "asia": "亞洲", "hong-kong": "香港", "japan": "日本",
    "finance": "財經 / 全球市場", "ai-tech": "AI / 科技",
    "manga-anime": "漫畫 / Anime", "manchester-united": "Manchester United",
    "football": "Football",
}
DESK_ROUTES = {
    "finance": ["market-economy"],
    "manchester-united": ["manchester-united", "football"],
}
PUBLIC_DESKS = tuple(DESK_LABELS)
TITLE_SUFFIX = re.compile(r"\s+(?:-|\||–|—)\s+[^|]{2,80}$")
BAD_TEXT = re.compile(r"[\ufffd]|[\ud800-\udfff]")
LOW_VALUE = re.compile(
    r"letter to the editor|opinion|commentary|stats?\s*&\s*head-to-head|"
    r"how to watch|live updates?|technical report available|photo gallery|圖片集|"
    r"交易資料|股市報價|大行.*評級",
    re.I,
)
MAN_UTD_NEWS = re.compile(
    r"injur|transfer|sign(?:ing|ed)?|deal|contract|squad|player|manager|coach|"
    r"match|fixture|goal|win|lose|lost|defeat|title|premier league|fa cup|champions league",
    re.I,
)
FOOTBALL_EVENT = re.compile(
    r"\b(?:beat|beats|beaten|defeat|defeats|draw|drew|win|wins|won|lose|lost|"
    r"sign|transfer|injur|goal|score|final|semi-final|qualif|champion|league|cup|"
    r"suspend|ban|resign|appoint|sack|launch|publish(?:es|ed)?)\b|擊敗|勝|負|和|入球|轉會|受傷|決賽|聯賽|盃",
    re.I,
)
TRUSTED_SOURCE = re.compile(
    r"reuters|associated press|\bap\b|bbc|sky sports|uefa|fifa|afc|goal\.com|"
    r"nhk|共同|時事通信|政府|gov\.|gov$|信報|香港電台|明報|經濟日報|kai-you|動畫",
    re.I,
)


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def parse_iso(value: Any) -> datetime | None:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if result.tzinfo is None:
            return None
        return result.astimezone(timezone.utc)
    except Exception:
        return None


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def story_time(story: dict[str, Any]) -> datetime | None:
    for key in ("publishedAt", "eventPublishedAt", "updatedAt", "verifiedAt"):
        stamp = parse_iso(story.get(key))
        if stamp:
            return stamp
    return None


def stale_desks(desk_data: dict[str, Any], now: datetime) -> list[str]:
    today = now.astimezone(HKT).date()
    desks = desk_data.get("desks") if isinstance(desk_data.get("desks"), dict) else {}
    stale: list[str] = []
    for producer_desk in PUBLIC_DESKS:
        public_desk = DESK_ROUTES.get(producer_desk, [producer_desk])[0]
        stories = desks.get(public_desk) if isinstance(desks.get(public_desk), list) else []
        timestamps = [story_time(row) for row in stories if isinstance(row, dict)]
        newest = max((stamp for stamp in timestamps if stamp is not None), default=None)
        if newest is None or newest.astimezone(HKT).date() < today:
            stale.append(producer_desk)
    return stale


def normalized_title(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff\u3040-\u30ff]+", " ", clean(value).lower()).strip()


def existing_identity(desk_data: dict[str, Any], live_data: dict[str, Any]) -> tuple[set[str], set[str]]:
    urls: set[str] = set()
    titles: set[str] = set()
    pools: list[Any] = list(live_data.get("items") or [])
    for rows in (desk_data.get("desks") or {}).values():
        if isinstance(rows, list):
            pools.extend(rows)
    for row in pools:
        if not isinstance(row, dict):
            continue
        url = clean(row.get("sourceUrl"))
        title = normalized_title(row.get("title"))
        if url:
            urls.add(url)
        if title:
            titles.add(title)
    return urls, titles


def candidate_ok(candidate: Any, desk: str, now: datetime, urls: set[str], titles: set[str]) -> bool:
    if not isinstance(candidate, dict) or clean(candidate.get("desk")) != desk:
        return False
    title = clean(candidate.get("title"))
    source = clean(candidate.get("source"))
    url = clean(candidate.get("url"))
    published = parse_iso(candidate.get("publishedAt"))
    if not title or not source or not url.startswith("http") or not published:
        return False
    if BAD_TEXT.search(title) or len(title) < 12:
        return False
    if LOW_VALUE.search(title):
        return False
    if desk == "hong-kong" and not re.search(r"香港|港聞|港股|港元|港府|港人|訪港|來港|在港|赴港|港交所|證監會|會財局|金管局|立法會|特區|陳茂波|陳翊庭|\bHong Kong\b|\bHK\b", title, re.I):
        return False
    if desk == "manchester-united" and not MAN_UTD_NEWS.search(title):
        return False
    if desk == "football" and not FOOTBALL_EVENT.search(title):
        return False
    if published > now + timedelta(minutes=10) or published.astimezone(HKT).date() != now.astimezone(HKT).date():
        return False
    return url not in urls and normalized_title(TITLE_SUFFIX.sub("", title)) not in titles


def select_candidate(staging: dict[str, Any], desk: str, now: datetime, urls: set[str], titles: set[str]) -> dict[str, Any] | None:
    rows = (staging.get("desks") or {}).get(desk) or []
    eligible = [row for row in rows if candidate_ok(row, desk, now, urls, titles)]
    normalized_counts: dict[str, int] = {}
    for row in eligible:
        key = normalized_title(TITLE_SUFFIX.sub("", clean(row.get("title"))))
        normalized_counts[key] = normalized_counts.get(key, 0) + 1

    def score(row: dict[str, Any]) -> tuple[int, float]:
        title = clean(row.get("title"))
        source = clean(row.get("source"))
        key = normalized_title(TITLE_SUFFIX.sub("", title))
        points = min(2, normalized_counts.get(key, 0) - 1) * 3
        if TRUSTED_SOURCE.search(source):
            points += 3
        if desk == "hong-kong" and re.search(r"香港|港府|港聞|訪港|來港|在港|港交所|證監會|會財局|金管局|立法會|特區", title):
            points += 2
        if desk == "manchester-united" and re.search(r"injur|transfer|sign|squad|manager|match", title, re.I):
            points += 2
        if desk == "football" and re.search(r"\b(?:beat|defeat|win|won|lost|goal|highlights?)\b|擊敗|勝|負|入球", title, re.I):
            points += 2
        stamp = parse_iso(row.get("publishedAt")) or datetime.min.replace(tzinfo=timezone.utc)
        return points, stamp.timestamp()

    eligible.sort(key=score, reverse=True)
    return eligible[0] if eligible else None


def display_title(candidate: dict[str, Any], desk: str) -> str:
    title = TITLE_SUFFIX.sub("", clean(candidate.get("title"))).strip(" -|–—")
    return title if re.search(r"[\u3400-\u9fff]", title) else f"{DESK_LABELS[desk]}消息：{title}"


def build_article(candidate: dict[str, Any], desk: str, now: datetime) -> dict[str, Any]:
    title = display_title(candidate, desk)
    original = TITLE_SUFFIX.sub("", clean(candidate.get("title"))).strip(" -|–—")
    source = clean(candidate.get("source"))
    published = parse_iso(candidate.get("publishedAt"))
    assert published is not None
    local_label = published.astimezone(HKT).strftime("%m月%d日 %H:%M HKT")
    digest = hashlib.sha1(f"{desk}\n{candidate.get('id')}\n{candidate.get('url')}".encode("utf-8")).hexdigest()[:12]
    routes = DESK_ROUTES.get(desk, [desk])
    body = (
        f"據{source}於{local_label}發布的報道，原文標題指出：「{original}」。"
        "這項更新只整理來源標題明確披露的事件，不加入標題以外而未獲公開來源支持的數字、引述或因果判斷。"
        "讀者可經原文連結核對發布機構、時間及最新修訂。\n\n"
        "事件仍可能隨官方聲明、當事人回應或後續報道而更新。"
        "如來源補充更多可核實資料，新聞頁會以新的發布時間、清楚來源及修訂內容跟進；在此之前，"
        "本條目的資訊邊界維持在上述標題直接支持的範圍。"
    )
    return {
        "id": f"general-{desk}-{digest}", "desk": routes[0], "deskSlugs": routes,
        "section": DESK_LABELS[desk], "sectionLabel": DESK_LABELS[desk], "title": title,
        "dek": f"{source}於{local_label}發布相關消息；現有稿件只採用來源標題可直接支持的內容。",
        "summary": f"{source}的報道標題指出「{original}」。以下更新保留原始來源及發布時間，方便讀者直接核對。",
        "body": body,
        "context": f"來源為{source}，原始發布時間為{local_label}；編採範圍限於來源標題可直接核實的資料。",
        "why": "這項消息屬於今日更新，能補回相應新聞頁缺少同日報道的情況，同時保留可追溯的原文來源。",
        "watchNext": "留意原發布機構、相關官方渠道及當事人其後公布的補充資料或更正。",
        "sourceName": source, "sourceUrl": clean(candidate.get("url")),
        "sources": [{"name": source, "url": clean(candidate.get("url"))}],
        "publishedAt": iso(published), "verifiedAt": iso(now),
        "timeLabel": now.astimezone(HKT).strftime("%m月%d日 %H:%M HKT核實"),
        "verification": {
            "mode": "source-headline-constrained", "candidateId": clean(candidate.get("id")),
            "provider": clean(candidate.get("provider")), "query": clean(candidate.get("query")),
            "originalTitle": clean(candidate.get("title")), "noUnsupportedDetail": True,
        },
    }


def target_time(now: datetime, current_live: datetime | None) -> datetime:
    target = now - timedelta(minutes=9)
    if current_live and target <= current_live:
        target = current_live + timedelta(minutes=1)
    return target.replace(second=0, microsecond=0)


def produce(staging: dict[str, Any], desk_data: dict[str, Any], live_data: dict[str, Any], now: datetime) -> dict[str, Any]:
    stale = stale_desks(desk_data, now)
    urls, titles = existing_identity(desk_data, live_data)
    articles: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}
    for desk in stale:
        candidate = select_candidate(staging, desk, now, urls, titles)
        if not candidate:
            skipped[desk] = "no-new-same-day-source-backed-candidate"
            continue
        article = build_article(candidate, desk, now)
        articles.append(article)
        urls.add(article["sourceUrl"])
        titles.add(normalized_title(article["title"]))
    current = parse_iso(live_data.get("lastUpdated"))
    target = target_time(now, current)
    stamp = now.astimezone(HKT).strftime("%Y%m%d-%H%M")
    return {
        "schemaVersion": 1, "status": "VERIFIED_DRAFT" if articles else "NO_PUBLISHABLE_UPDATE",
        "publicationType": "LIVE", "producer": "General News Verified Producer",
        "draftId": f"general-news-{stamp}-hkt", "createdAt": iso(now),
        "targetPublication": target.astimezone(HKT).isoformat(),
        "leadId": articles[0]["id"] if articles else None, "articles": articles,
        "coverage": {
            "staleDesks": stale, "producedDesks": [row["desk"] for row in articles],
            "skippedDesks": skipped,
            "candidateSnapshotAt": staging.get("lastSearchAt") or staging.get("lastSearchStartedAt"),
            "verificationMode": "source-headline-constrained",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("staging", type=Path)
    parser.add_argument("--desk", type=Path, default=Path("data/desk-latest.json"))
    parser.add_argument("--live", type=Path, default=Path("data/live.json"))
    parser.add_argument("--output", type=Path, default=Path("/tmp/general-news-prepublish.json"))
    parser.add_argument("--now", default="")
    args = parser.parse_args()
    now = parse_iso(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        raise SystemExit("--now must be a timezone-aware ISO timestamp")
    result = produce(load(args.staging), load(args.desk), load(args.live), now)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("GENERAL_NEWS_PRODUCER_" + ("PASS" if result["articles"] else "NOOP"),
          f"stale={len(result['coverage']['staleDesks'])}", f"produced={len(result['articles'])}",
          f"skipped={len(result['coverage']['skippedDesks'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
