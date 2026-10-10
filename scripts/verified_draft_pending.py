"""Retain an unconsumed verified draft through its existing publication slot.

This is scheduling ownership, not publication permission. The publisher keeps
its original grace/90-minute gate; original story dates and quality stay intact.
"""
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

HKT = timezone(timedelta(hours=8))


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
    except (ValueError, TypeError):
        return None


def pending_verified_draft(draft, now, live=None):
    if draft.get("status") != "VERIFIED_DRAFT" or draft.get("publicationType") != "LIVE":
        return False
    articles = draft.get("articles")
    if not isinstance(articles, list) or not articles:
        return False
    if draft_has_locator_only_sources(draft):
        return False
    draft_id = str(draft.get("draftId") or "").strip()
    consumed = str(((live or {}).get("coverage") or {}).get("verifiedDraftId") or "").strip()
    if draft_id and draft_id == consumed:
        return False
    created = stamp(draft.get("createdAt"))
    if created is None or not 0 <= (now - created).total_seconds():
        return False
    if now - created <= timedelta(minutes=120):
        return True

    # Only the canonical overnight/08:00 skip can outlive discovery's old
    # two-hour guard. Arbitrary future targets cannot reserve production.
    local = created.astimezone(HKT)
    if 1 <= local.hour <= 5:
        expected = local.replace(hour=6, minute=0, second=0, microsecond=0)
    elif local.hour == 8:
        expected = local.replace(hour=9, minute=0, second=0, microsecond=0)
    else:
        return False
    target = stamp(draft.get("targetPublication"))
    if not draft_id or target != expected.astimezone(timezone.utc):
        return False
    if now > target + timedelta(minutes=90):
        return False
    # Holding a scheduled draft must not preserve already-stale/future copy.
    # No verification or scheduled clock substitutes for publication time.
    for article in articles:
        published = stamp(article.get("publishedAt")) if isinstance(article, dict) else None
        if published is None or not 0 <= (now - published).total_seconds() <= 24 * 3600:
            return False
    return True
