#!/usr/bin/env python3
"""Shared newsroom retention policy for Rolling Desk stories.

The Rolling Desk is a current-news surface, not an archive.  Stories may be
cross-routed while they are fresh (for example J-League on Japan + Football),
but a sports cross-post must not linger on a geographic desk for days merely
because that desk has not reached its numeric cap.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

HKT = timezone(timedelta(hours=8))
JST = timezone(timedelta(hours=9))
CROSS_DESK_FOOTBALL_TTL = timedelta(hours=36)


def parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def story_time(story: dict[str, Any], *, now: datetime | None = None) -> datetime | None:
    """Return the best available publication/update timestamp in UTC.

    Explicit structured timestamps win.  For legacy Rolling Desk stories, IDs
    and human time labels are used conservatively.  A date-only ID is treated as
    23:59 HKT on that date so it cannot expire prematurely.
    """
    for key in ("publishedAt", "updatedAt", "timestamp", "time", "verifiedAt"):
        dt = parse_iso(story.get(key))
        if dt:
            return dt

    ident = str(story.get("id") or "")
    # IDs ending YYYYMMDD-HHMM / YYYYMMDDHHMM / YYYYMMDD_HHMM.
    m = re.search(r"(20\d{6})[-_]?([0-2]\d)([0-5]\d)$", ident)
    if m:
        try:
            return datetime.strptime("".join(m.groups()), "%Y%m%d%H%M").replace(tzinfo=HKT).astimezone(timezone.utc)
        except ValueError:
            pass

    # Legacy IDs ending only in YYYYMMDD.  End-of-day is intentionally used.
    m = re.search(r"(20\d{6})$", ident)
    if m:
        try:
            dt = datetime.strptime(m.group(1), "%Y%m%d").replace(hour=23, minute=59, second=59, tzinfo=HKT)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass

    label = str(story.get("timeLabel") or "")
    base_now = (now or datetime.now(timezone.utc)).astimezone(HKT)
    year = base_now.year

    # HKT labels used by most desks.
    m = re.search(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s*HKT", label, re.I)
    if m:
        month, day, hour, minute = map(int, m.groups())
        try:
            candidate = datetime(year, month, day, hour, minute, tzinfo=HKT)
            if candidate - base_now > timedelta(days=2):
                candidate = candidate.replace(year=year - 1)
            return candidate.astimezone(timezone.utc)
        except ValueError:
            pass

    # Japan desk sometimes records JST explicitly.
    m = re.search(r"(\d{1,2})月(\d{1,2})日\s*(\d{1,2}):(\d{2})\s*JST", label, re.I)
    if m:
        month, day, hour, minute = map(int, m.groups())
        try:
            candidate = datetime(year, month, day, hour, minute, tzinfo=JST)
            now_jst = (now or datetime.now(timezone.utc)).astimezone(JST)
            if candidate - now_jst > timedelta(days=2):
                candidate = candidate.replace(year=year - 1)
            return candidate.astimezone(timezone.utc)
        except ValueError:
            pass

    return None


def routed_slugs(story: dict[str, Any]) -> list[str]:
    raw = story.get("deskSlugs")
    if isinstance(raw, list):
        return [str(x) for x in raw if str(x)]
    desk = str(story.get("desk") or "").strip()
    return [desk] if desk else []


def is_cross_routed_football(story: dict[str, Any], target_slug: str) -> bool:
    """True when a Football story is being shown on another topical desk."""
    if target_slug in {"football", "manchester-united"}:
        return False
    routes = routed_slugs(story)
    primary = str(story.get("desk") or "").strip()
    return "football" in routes or primary == "football"


def expired_cross_desk_football(
    story: dict[str, Any],
    target_slug: str,
    *,
    now: datetime | None = None,
    ttl: timedelta = CROSS_DESK_FOOTBALL_TTL,
) -> bool:
    """Expire stale Football cross-posts from non-Football desks.

    The story remains on the Football desk.  Unparseable timestamps are retained
    rather than silently deleted; the supervisory audit can flag malformed data.
    """
    if not is_cross_routed_football(story, target_slug):
        return False
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    current = current.astimezone(timezone.utc)
    stamp = story_time(story, now=current)
    if stamp is None:
        return False
    return current - stamp > ttl


def keep_on_desk(story: dict[str, Any], target_slug: str, *, now: datetime | None = None) -> bool:
    return not expired_cross_desk_football(story, target_slug, now=now)
