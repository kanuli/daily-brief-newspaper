#!/usr/bin/env python3
"""Build the required Daily Edition from already-verified Rolling Desk stories.

This is a recovery path, not a news generator. It never invents copy and never
retimestamps old stories. It copies current, already-published newsroom stories
from data/desk-latest.json into the required Daily Edition when the normal Daily
publisher has failed to advance data/latest.json.

At or after 08:00 HKT the required edition is today's Daily. Before 08:00 HKT,
yesterday remains the canonical Daily; if yesterday's edition itself is missing,
this recovery path builds that missing edition instead of incorrectly returning
NOOP and leaving a two-day-old Daily to block GitHub Pages.

Recovery deliberately re-runs the Daily public-copy gate on every candidate.
One contaminated Rolling Desk story must be skipped, not allowed to freeze the
entire Daily publication.
"""
from __future__ import annotations

import argparse
import copy
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

from desk_freshness_policy import editorial_story_time
from validate_daily_v3 import validate_story

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
HKT = timezone(timedelta(hours=8))
DAILY_OPEN_HOUR_HKT = 8

DESK_ORDER = (
    "world", "asia", "hong-kong", "japan", "market-economy",
    "ai-tech", "manga-anime", "manchester-united", "football",
)
SLA_HOURS = {
    "world": 24, "asia": 24, "hong-kong": 24, "japan": 24,
    "market-economy": 24, "ai-tech": 24,
    "manga-anime": 48, "manchester-united": 48, "football": 48,
}
SECTION_META = {
    "world": ("世界", "非亞洲國際政治、社會、外交、安全、氣候與公共事務"),
    "asia": ("亞洲", "東亞、東南亞、南亞、中亞、西亞／中東"),
    "hong-kong": ("香港", "香港公共事務、社會、民生與城市發展"),
    "japan": ("日本", "日本政治、社會、經濟、公共安全與民生"),
    "market-economy": ("財經", "全球市場、宏觀經濟、企業與產業"),
    "ai-tech": ("AI / 科技", "人工智能、半導體、平台、科研與科技產業"),
    "manga-anime": ("漫畫 / Anime", "漫畫、動畫、出版、製作與產業動態"),
    "manchester-united": ("Manchester United", "曼聯球會、賽事、球員與管理層"),
    "football": ("Football", "全球足球賽事、球會、國家隊、轉會與監管"),
}
WEEKDAY_ZH = ("星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def current_story(story: dict[str, Any], slug: str, reference: datetime) -> bool:
    stamp = editorial_story_time(story, now=reference)
    if stamp is None:
        return False
    # A catch-up edition must never pull a story from after that edition's
    # editorial cutoff. This prevents 28 Sep overnight stories appearing in a
    # recovered 27 Sep Daily merely because the current desk already contains them.
    if stamp > reference:
        return False
    age_seconds = (reference - stamp).total_seconds()
    return 0 <= age_seconds <= SLA_HOURS[slug] * 3600


def story_stamp(story: dict[str, Any], reference: datetime) -> datetime:
    stamp = editorial_story_time(story, now=reference)
    if stamp is None or stamp > reference:
        return datetime.min.replace(tzinfo=timezone.utc)
    return stamp


def daily_candidate(story: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Return a Daily-safe copy, or the exact validation reason for rejection."""
    copied = copy.deepcopy(story)
    copied.pop("status", None)
    sid = str(copied.get("id") or "<missing-id>")
    try:
        validate_story(copied, f"Daily recovery candidate id={sid}")
    except Exception as exc:
        return None, str(exc)
    return copied, None


def required_daily_target(now_hkt: datetime) -> tuple[str, datetime, str]:
    """Return edition date, editorial cutoff/reference, and recovery mode."""
    if now_hkt.hour >= DAILY_OPEN_HOUR_HKT:
        target_date = now_hkt.date()
        reference_hkt = now_hkt
        mode = "TODAY_FIRST_FROM_VERIFIED_ROLLING_DESK"
    else:
        target_date = now_hkt.date() - timedelta(days=1)
        # The prior-day catch-up may use only stories that existed by the end of
        # that calendar day. Current overnight stories are excluded.
        reference_hkt = datetime.combine(target_date, time(23, 59, 59), tzinfo=HKT)
        mode = "PRIOR_DAY_CATCHUP_FROM_VERIFIED_ROLLING_DESK"
    return target_date.isoformat(), reference_hkt.astimezone(timezone.utc), mode


def build(now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    actual_now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    now_hkt = actual_now.astimezone(HKT)
    target, reference, recovery_mode = required_daily_target(now_hkt)
    target_date = datetime.fromisoformat(target).date()

    latest_path = DATA / "latest.json"
    previous = load(latest_path)
    previous_date = str(previous.get("date") or "")

    if previous_date >= target:
        reason = "daily-already-current" if previous_date == target else "daily-newer-than-required-target"
        return previous, {
            "changed": False,
            "reason": reason,
            "date": target,
            "existingDate": previous_date,
            "dailyOpenHourHKT": DAILY_OPEN_HOUR_HKT,
        }

    desk_path = DATA / "desk-latest.json"
    desk = load(desk_path)
    desk_date = str(desk.get("date") or "")
    effective_desk_date = desk_date
    generated_at = str(desk.get("generatedAt") or desk.get("lastUpdated") or "")
    if generated_at:
        try:
            generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            if generated.tzinfo is not None:
                generated_date = generated.astimezone(HKT).date().isoformat()
                if generated_date > effective_desk_date:
                    effective_desk_date = generated_date
        except Exception:
            pass
    if effective_desk_date < target:
        raise SystemExit(
            f"Rolling Desk is not current enough to build required Daily: "
            f"desk date={desk_date} generatedAt={generated_at or 'missing'} "
            f"effective date={effective_desk_date} required={target}"
        )

    desks = desk.get("desks") if isinstance(desk.get("desks"), dict) else {}
    selected_by_desk: dict[str, list[dict[str, Any]]] = {}
    seen: set[str] = set()
    rejected: list[dict[str, str]] = []

    # Take up to two genuinely current, Daily-safe stories from each healthy
    # desk, evaluated at this edition's editorial cutoff. A bad candidate is
    # skipped and the next candidate is tried.
    for slug in DESK_ORDER:
        rows = desks.get(slug) if isinstance(desks.get(slug), list) else []
        current = [s for s in rows if isinstance(s, dict) and current_story(s, slug, reference)]
        current.sort(key=lambda s: story_stamp(s, reference), reverse=True)
        picked: list[dict[str, Any]] = []
        for story in current:
            sid = str(story.get("id") or "").strip()
            if not sid or sid in seen:
                continue
            copied, error = daily_candidate(story)
            if copied is None:
                rejected.append({"desk": slug, "id": sid, "reason": error or "invalid-public-copy"})
                continue
            picked.append(copied)
            seen.add(sid)
            if len(picked) >= 2:
                break
        if picked:
            selected_by_desk[slug] = picked

    articles = [s for slug in DESK_ORDER for s in selected_by_desk.get(slug, [])]
    articles.sort(key=lambda s: story_stamp(s, reference), reverse=True)
    if len(articles) < 8:
        raise SystemExit(
            f"Only {len(articles)} current Daily-safe Rolling Desk stories available for {target}; "
            f"refusing weak Daily catch-up; rejected={len(rejected)}"
        )

    sections = []
    for slug in DESK_ORDER:
        rows = selected_by_desk.get(slug, [])
        if not rows:
            continue
        title, subtitle = SECTION_META[slug]
        sections.append({
            "slug": slug,
            "title": title,
            "label": title,
            "subtitle": subtitle,
            "articleIds": [s["id"] for s in rows],
        })

    try:
        edition = int(str(previous.get("editionNumber") or "0")) + 1
    except ValueError:
        edition = 1
    top_ids = [s["id"] for s in articles[:5]]
    headline_titles = [str(s.get("title") or "").strip() for s in articles[:3] if s.get("title")]

    # generatedAt records the real recovery execution time. The edition date is
    # the required canonical Daily date; story timestamps remain untouched.
    generated_hkt = actual_now.astimezone(HKT)
    daily = {
        "editionNumber": f"{edition:03d}",
        "date": target,
        "dateLabel": f"{target_date.year}年{target_date.month}月{target_date.day}日 {WEEKDAY_ZH[target_date.weekday()]}",
        "tagline": f"{target_date.month}月{target_date.day}日今日最新新聞 · v3長文",
        "editorialStandardVersion": 3,
        "contentVersion": 3,
        "generatedAt": generated_hkt.replace(microsecond=0).isoformat(),
        "recoveryMode": recovery_mode,
        "leadId": articles[0]["id"],
        "topFive": top_ids,
        "articles": articles,
        "sections": sections,
    }
    meta = {
        "changed": True,
        "date": target,
        "articleCount": len(articles),
        "leadId": daily["leadId"],
        "topFive": top_ids,
        "headline": "；".join(headline_titles),
        "recoveryMode": recovery_mode,
        "omittedStaleDesks": [slug for slug in DESK_ORDER if slug not in selected_by_desk],
        "rejectedInvalidStories": rejected,
    }
    return daily, meta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--now", help="ISO time for tests")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else None
    daily, meta = build(now)
    if args.write and meta.get("changed"):
        edition_date = daily["date"]
        dump(DATA / "latest.json", daily)
        dump(DATA / f"{edition_date}.json", daily)
        # Topic-more is deliberately the same verified current reservoir for the
        # catch-up edition. Normal Daily production may expand it on later runs.
        dump(DATA / "topic-more" / f"{edition_date}.json", daily)
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
