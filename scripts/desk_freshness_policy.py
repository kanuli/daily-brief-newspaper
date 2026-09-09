#!/usr/bin/env python3
"""Shared public-desk freshness and editorial-routing policy.

Numeric desk depth is not enough to prove that a public news page is current.
A story also has to belong to the page. Publication uses one primary desk by
default; cross-desk relevance is context, not a licence to duplicate a story
onto unrelated topic pages. Specialist football and manga/anime ownership is
resolved before generic geographic/business routing.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from desk_retention import parse_iso, story_time

HKT = timezone(timedelta(hours=8))
JST = timezone(timedelta(hours=9))

EXPECTED_DESKS = (
    "world", "asia", "hong-kong", "japan", "market-economy",
    "ai-tech", "manga-anime", "manchester-united", "football",
)

PUBLIC_DESK_FRESHNESS_HOURS = {
    "world": 8,
    "asia": 12,
    "hong-kong": 12,
    "japan": 12,
    "market-economy": 8,
    "ai-tech": 12,
    "manga-anime": 24,
    "manchester-united": 24,
    "football": 8,
}

CAPS = {
    "world": 24,
    "asia": 24,
    "hong-kong": 16,
    "japan": 20,
    "market-economy": 20,
    "ai-tech": 20,
    "manga-anime": 12,
    "manchester-united": 10,
    "football": 24,
}

CANONICAL_DESK = {"finance": "market-economy"}

_FOOTBALL = re.compile(
    r"(?:\bfootball\b|\bsoccer\b|\bFIFA\b|\bUEFA\b|\bAFC\b|\bPremier League\b|"
    r"\bChampions League\b|\bEuropa League\b|\bJ[- ]?League\b|\bU-?20\b.{0,25}(?:World Cup|世界盃)|"
    r"世界盃|世盃|足球|英超|歐聯|歐霸|日職|J聯賽|女足|女子世界盃|球賽|入球|轉會|領隊|球員)",
    re.I,
)
_MANCHESTER_UNITED = re.compile(
    r"(?:Manchester United|Man Utd|Man United|曼聯|曼彻斯特联|紅魔)", re.I,
)
_MANGA_ANIME = re.compile(
    r"(?:\banime\b|\bmanga\b|漫畫|动画|動畫|動漫|漫改|輕小說|聲優|名偵探柯南|柯南|"
    r"聖鬥士星矢|One Piece|海賊王|鬼滅之刃|咒術迴戰|進擊的巨人)",
    re.I,
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def canonical_slug(value: Any) -> str:
    raw = str(value or "").strip()
    return CANONICAL_DESK.get(raw, raw)


def _routing_text(story: dict[str, Any]) -> str:
    return " ".join(
        str(story.get(key) or "")
        for key in ("id", "desk", "section", "sectionLabel", "title", "dek", "summary")
    )


def routed_slugs(story: dict[str, Any]) -> list[str]:
    """Return editorial publication ownership for a story.

    The first valid explicit deskSlugs entry is the primary desk. Secondary
    deskSlugs are treated as relevance metadata only and do not cause public
    cross-posting. Clear specialist content overrides a generic geographic or
    finance tag so football cannot leak into World/Asia/Japan/Finance and
    manga/anime cannot leak into Japan/general desks. Manchester United-specific
    football belongs to both its dedicated MU desk and the general Football desk.

    Daily v3 story IDs are also accepted as explicit primary-desk ownership.
    This keeps verified Daily copy routable even when a producer omits legacy
    ``desk`` metadata; specialist content still wins before generic ID routing.
    """
    text = _routing_text(story)
    story_id = str(story.get("id") or "").strip().lower()
    raw_desk = canonical_slug(story.get("desk"))

    is_mu = (
        raw_desk == "manchester-united"
        or story_id.startswith(("mu-", "manchester-united-"))
        or bool(_MANCHESTER_UNITED.search(text))
    )
    is_football = (
        raw_desk in {"football", "manchester-united"}
        or story_id.startswith(("football-", "soccer-", "fifa-", "uefa-"))
        or bool(_FOOTBALL.search(text))
    )
    if is_mu and is_football:
        return ["manchester-united", "football"]
    if is_football:
        return ["football"]

    is_manga = (
        raw_desk == "manga-anime"
        or story_id.startswith(("anime-", "manga-", "comic-"))
        or bool(_MANGA_ANIME.search(text))
    )
    if is_manga:
        return ["manga-anime"]

    explicit = story.get("deskSlugs")
    if isinstance(explicit, list) and explicit:
        for raw in explicit:
            slug = canonical_slug(raw)
            if slug in EXPECTED_DESKS:
                return [slug]

    if raw_desk in EXPECTED_DESKS:
        return [raw_desk]

    # Daily v3 canonical IDs carry primary desk ownership. This fallback is
    # deliberately after football/manga classification so specialist stories
    # can never leak into a geographic or market desk merely because of an ID.
    id_prefixes = (
        ("manchester-united-", "manchester-united"),
        ("hong-kong-", "hong-kong"),
        ("market-economy-", "market-economy"),
        ("market-", "market-economy"),
        ("ai-tech-", "ai-tech"),
        ("manga-anime-", "manga-anime"),
        ("world-", "world"),
        ("asia-", "asia"),
        ("japan-", "japan"),
    )
    for prefix, slug in id_prefixes:
        if story_id.startswith(prefix):
            return [slug]
    return []


def editorial_story_time(story: dict[str, Any], *, now: datetime | None = None) -> datetime | None:
    """Resolve the best editorial timestamp without faking end-of-day freshness.

    Daily story IDs often end in a date only. The generic retention parser treats
    such IDs as 23:59 HKT so it will not delete them prematurely. That behavior is
    correct for retention but wrong for freshness. Here an explicit timestamp or
    human editorial timeLabel takes precedence over a date-only ID.
    """
    current = (now or now_utc()).astimezone(timezone.utc)
    for key in ("publishedAt", "updatedAt", "timestamp", "time", "verifiedAt"):
        stamp = parse_iso(story.get(key))
        if stamp is not None:
            return stamp

    label = str(story.get("timeLabel") or "")
    current_hkt = current.astimezone(HKT)
    year = current_hkt.year
    for zone_name, zone in (("HKT", HKT), ("JST", JST)):
        m = re.search(rf"(\d{{1,2}})月(\d{{1,2}})日\s*(\d{{1,2}}):(\d{{2}})\s*{zone_name}", label, re.I)
        if not m:
            continue
        month, day, hour, minute = map(int, m.groups())
        try:
            candidate = datetime(year, month, day, hour, minute, tzinfo=zone)
            current_local = current.astimezone(zone)
            if candidate - current_local > timedelta(days=2):
                candidate = candidate.replace(year=year - 1)
            return candidate.astimezone(timezone.utc)
        except ValueError:
            pass

    return story_time(story, now=current)


def freshest_story_time(stories: list[dict[str, Any]], *, now: datetime | None = None) -> datetime | None:
    current = now or now_utc()
    stamps = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        stamp = editorial_story_time(story, now=current)
        if stamp is not None:
            stamps.append(stamp)
    return max(stamps) if stamps else None


def newest_age_hours(stories: list[dict[str, Any]], *, now: datetime | None = None) -> float | None:
    current = (now or now_utc()).astimezone(timezone.utc)
    stamp = freshest_story_time(stories, now=current)
    if stamp is None:
        return None
    return max(0.0, (current - stamp).total_seconds() / 3600.0)


def desk_is_fresh(slug: str, stories: list[dict[str, Any]], *, now: datetime | None = None) -> bool:
    age = newest_age_hours(stories, now=now)
    return age is not None and age <= PUBLIC_DESK_FRESHNESS_HOURS[slug]


def current_daily_dates(*, now: datetime | None = None) -> set[str]:
    """Dates acceptable for data/latest.json at the current HKT slot.

    Before the 08:00 Daily handover finishes, yesterday's edition remains the
    valid baseline. After 08:15, only today's Daily edition is current.
    """
    current = (now or now_utc()).astimezone(HKT)
    today = current.date()
    if current.hour < 8 or (current.hour == 8 and current.minute < 15):
        return {today.isoformat(), (today - timedelta(days=1)).isoformat()}
    return {today.isoformat()}
