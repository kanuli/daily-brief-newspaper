#!/usr/bin/env python3
"""Promote a verified prepublish LIVE draft only when main Live is behind.

This is an emergency publication failover. It never invents news and never
promotes raw discovery candidates: input must already be VERIFIED_DRAFT.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIVE_PATH = DATA / "live.json"
LATEST_PATH = DATA / "latest.json"

REQUIRED = (
    "id", "title", "dek", "summary", "body", "context", "why",
    "watchNext", "sourceName", "sourceUrl", "timeLabel",
)

DESK_SLUGS = {
    "world": ["world"],
    "asia": ["asia"],
    "hong-kong": ["hong-kong"],
    "japan": ["japan"],
    "finance": ["market-economy"],
    "market-economy": ["market-economy"],
    "stock-news": [],
    "ai-tech": ["ai-tech"],
    "manga-anime": ["manga-anime"],
    "manchester-united": ["manchester-united"],
    "football": ["football"],
}

SECTIONS = {
    "world": "世界",
    "asia": "亞洲",
    "hong-kong": "香港",
    "japan": "日本",
    "finance": "財經",
    "market-economy": "財經",
    "stock-news": "Stock News",
    "ai-tech": "AI / 科技",
    "manga-anime": "漫畫 / Anime",
    "manchester-united": "Manchester United",
    "football": "Football",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"timestamp must include timezone: {value}")
    return dt


def clean(value):
    return " ".join(str(value or "").split())


def display_hour(target: datetime, daily_date: str) -> int:
    # Midnight closes the previous Daily date's publication window as 24:00.
    if target.hour == 0 and target.date().isoformat() != daily_date:
        return 24
    return target.hour


def next_update_label(hour: int) -> str:
    if hour == 7:
        return "下一輪預定 09:00 HKT（08:00 Daily Edition）"
    if hour >= 24:
        return "下一輪預定 06:00 HKT"
    return f"下一輪預定 {hour + 1:02d}:00 HKT"


def validate_draft(draft, now: datetime, grace_minutes: int, max_age_minutes: int):
    if draft.get("status") != "VERIFIED_DRAFT":
        raise SystemExit("FAILOVER_SKIP draft is not VERIFIED_DRAFT")
    if draft.get("publicationType") != "LIVE":
        raise SystemExit("FAILOVER_SKIP draft publicationType is not LIVE")
    target = parse_iso(draft.get("targetPublication") or "")
    due = target + timedelta(minutes=grace_minutes)
    if now < due.astimezone(timezone.utc):
        raise SystemExit(f"FAILOVER_SKIP target not past grace: {target.isoformat()}")
    if now - target.astimezone(timezone.utc) > timedelta(minutes=max_age_minutes):
        raise SystemExit(f"FAILOVER_SKIP draft too old: {target.isoformat()}")
    articles = draft.get("articles")
    if not isinstance(articles, list) or not articles:
        raise SystemExit("FAILOVER_SKIP verified draft has no articles")
    for index, article in enumerate(articles):
        if not isinstance(article, dict):
            raise SystemExit(f"draft[{index}] is not an object")
        for field in REQUIRED:
            if not clean(article.get(field)):
                raise SystemExit(f"draft[{index}] missing {field}")
        if "\n\n" not in str(article.get("body") or ""):
            raise SystemExit(f"draft[{index}] body needs two paragraphs")
    return target, articles


def build_live(draft, old_live, latest, target, articles):
    daily_date = str(latest.get("date") or old_live.get("date") or target.date().isoformat())
    hour = display_hour(target, daily_date)
    old_by_id = {
        str(item.get("id")): item
        for item in (old_live.get("items") or [])
        if isinstance(item, dict) and item.get("id")
    }

    items = []
    counts = {"NEW": 0, "UPDATED": 0, "DEVELOPING": 0}
    for source in articles:
        item = copy.deepcopy(source)
        article_id = str(item.get("id") or "")
        requested = str(item.get("status") or "").upper()
        if requested == "DEVELOPING":
            status = "DEVELOPING"
        else:
            status = "UPDATED" if article_id in old_by_id else "NEW"
        item["status"] = status
        counts[status] += 1

        desk = str(item.get("desk") or "")
        slugs = item.get("deskSlugs")
        if not isinstance(slugs, list):
            slugs = DESK_SLUGS.get(desk, [])
        item["deskSlugs"] = list(dict.fromkeys(str(x) for x in slugs if x))
        if not clean(item.get("section")):
            item["section"] = SECTIONS.get(desk, "Live")
        items.append(item)

    coverage = copy.deepcopy(old_live.get("coverage") or {})
    coverage.update({
        "status": "COMPLETE",
        "publicationFailoverUsed": True,
        "publicationSource": "verified-prepublish-draft",
        "verifiedDraftId": draft.get("draftId"),
        "verifiedDraftCreatedAt": draft.get("createdAt"),
    })

    return {
        "mode": "live",
        "date": daily_date,
        "editorialStandardVersion": 3,
        "contentVersion": 3,
        "lastUpdated": target.isoformat(),
        "lastUpdatedLabel": f"{daily_date[:4]}年{int(daily_date[5:7])}月{int(daily_date[8:10])}日 {hour:02d}:00 HKT",
        "nextUpdateLabel": next_update_label(hour),
        "windowLabel": f"{hour:02d}:00 HKT Live Update",
        "newCount": counts["NEW"],
        "updatedCount": counts["UPDATED"],
        "developingCount": counts["DEVELOPING"],
        "coverage": coverage,
        "leadId": draft.get("leadId"),
        "items": items,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("draft")
    parser.add_argument("--grace-minutes", type=int, default=8)
    parser.add_argument("--max-age-minutes", type=int, default=90)
    parser.add_argument("--now", default="")
    args = parser.parse_args()

    now = parse_iso(args.now).astimezone(timezone.utc) if args.now else datetime.now(timezone.utc)
    draft = load(Path(args.draft))
    old_live = load(LIVE_PATH)
    latest = load(LATEST_PATH)
    target, articles = validate_draft(draft, now, args.grace_minutes, args.max_age_minutes)

    try:
        current = parse_iso(old_live.get("lastUpdated") or "")
    except Exception:
        current = datetime.min.replace(tzinfo=timezone.utc)
    if current.astimezone(timezone.utc) >= target.astimezone(timezone.utc):
        print(f"FAILOVER_NOOP current={current.isoformat()} target={target.isoformat()}")
        return 0

    live = build_live(draft, old_live, latest, target, articles)
    LIVE_PATH.write_text(json.dumps(live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "VERIFIED_LIVE_FAILOVER_PROMOTED",
        f"draft={draft.get('draftId')}",
        f"target={target.isoformat()}",
        f"items={len(live['items'])}",
        f"new={live['newCount']}",
        f"updated={live['updatedCount']}",
        f"developing={live['developingCount']}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
