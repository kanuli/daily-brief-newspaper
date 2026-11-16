"""Retain an unconsumed verified draft through its existing publication slot.

This is scheduling ownership, not publication permission. The publisher keeps
its original grace/90-minute gate; original story dates and quality stay intact.
"""
from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlparse

if __package__:
    from .general_news_verified_producer import HKT, target_time
else:
    from general_news_verified_producer import HKT, target_time


DRAFT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")


def locator_only_url(value):
    """NewsPicks summaries/reader picks are locators, not publisher evidence."""
    try:
        host = (urlparse(str(value or "")).hostname or "").lower().rstrip(".")
    except ValueError:
        return True
    return host == "newspicks.com" or host.endswith(".newspicks.com")


def draft_has_locator_only_sources(draft):
    for article in draft.get("articles") or []:
        if not isinstance(article, dict):
            continue
        if locator_only_url(article.get("sourceUrl")):
            return True
        for source in article.get("sources") or []:
            if isinstance(source, dict) and locator_only_url(source.get("url")):
                return True
    return False


def stamp(value):
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(timezone.utc) if result.tzinfo is not None else None
    except (ValueError, TypeError, OverflowError):
        return None


def pending_verified_draft(draft, now, live=None):
    """Recompute the Producer slot; reservation is never a publishing permit."""
    if not isinstance(draft, dict) or not isinstance(now, datetime) or now.utcoffset() is None:
        return False
    if draft.get("status") != "VERIFIED_DRAFT" or draft.get("publicationType") != "LIVE":
        return False
    draft_id = draft.get("draftId")
    created = stamp(draft.get("createdAt"))
    target = stamp(draft.get("targetPublication"))
    if not isinstance(draft_id, str) or DRAFT_ID.fullmatch(draft_id) is None:
        return False
    now = now.astimezone(timezone.utc)
    if created is None or target is None or created > now:
        return False

    if live is not None and not isinstance(live, dict):
        return False
    live = live or {}
    coverage = live.get("coverage")
    if isinstance(coverage, dict) and coverage.get("verifiedDraftId") == draft_id:
        return False
    live_value = live.get("lastUpdated")
    current = stamp(live_value)
    if live_value not in (None, "") and current is None:
        return False
    if current is not None and (current > now or target <= current):
        return False

    # Match the repository Producer's exact minute, including normal slots,
    # skipped hours, and the existing catastrophic-staleness fallback.
    try:
        expected_target = target_time(created, current)
    except OverflowError:
        return False
    if target != expected_target or now - target > timedelta(minutes=90):
        return False

    articles = draft.get("articles")
    if not isinstance(articles, list) or not articles:
        return False
    for article in articles:
        if not isinstance(article, dict) or not isinstance(article.get("sources") or [], list):
            return False
        published = stamp(article.get("publishedAt"))
        if published is None or not 0 <= (now - published).total_seconds() <= 24 * 3600:
            return False
    if draft_has_locator_only_sources(draft):
        return False
    if now - created <= timedelta(minutes=120):
        return True

    # The only long reservations in the existing discovery contract are
    # overnight -> 06:00 HKT and the 08:00 -> 09:00 HKT skip.
    local = created.astimezone(HKT)
    if 1 <= local.hour <= 5:
        expected = local.replace(hour=6, minute=0, second=0, microsecond=0)
    elif local.hour == 8:
        expected = local.replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        return False
    return target == expected
