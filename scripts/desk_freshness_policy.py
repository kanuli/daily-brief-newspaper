#!/usr/bin/env python3
"""Shared public-desk freshness policy.

Numeric desk depth is not enough to prove that a public news page is current.
This module defines the maximum age of the newest published/verified story that
may still be described as a healthy current desk.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from desk_retention import story_time

HKT = timezone(timedelta(hours=8))

EXPECTED_DESKS = (
    "world", "asia", "hong-kong", "japan", "market-economy",
    "ai-tech", "manga-anime", "manchester-united", "football",
)

# Public-page SLA, not a collection lookback. Niche desks may have a longer
# window than broad breaking-news desks, but no desk may silently survive for
# multiple days merely because it still contains enough old stories.
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


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def canonical_slug(value: Any) -> str:
    raw = str(value or "").strip()
    return CANONICAL_DESK.get(raw, raw)


def routed_slugs(story: dict[str, Any]) -> list[str]:
    explicit = story.get("deskSlugs")
    if isinstance(explicit, list) and explicit:
        out = []
        for raw in explicit:
            slug = canonical_slug(raw)
            if slug in EXPECTED_DESKS and slug not in out:
                out.append(slug)
        if out:
            return out
    slug = canonical_slug(story.get("desk"))
    return [slug] if slug in EXPECTED_DESKS else []


def freshest_story_time(stories: list[dict[str, Any]], *, now: datetime | None = None) -> datetime | None:
    current = now or now_utc()
    stamps = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        stamp = story_time(story, now=current)
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
