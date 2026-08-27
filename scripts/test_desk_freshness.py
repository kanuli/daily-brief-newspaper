#!/usr/bin/env python3
from datetime import datetime, timezone

from validate_desk_freshness import audit

NOW = datetime(2026, 8, 28, 0, 30, tzinfo=timezone.utc)
SLUGS = (
    "world", "asia", "hong-kong", "japan", "market-economy",
    "ai-tech", "manga-anime", "manchester-united", "football",
)


def story(slug, ident):
    return {
        "id": ident,
        "desk": slug,
        "deskSlugs": [slug],
        "title": f"{slug} 測試新聞",
        "summary": "測試摘要",
        "body": "測試正文",
        "sourceUrl": "https://example.com",
    }


def base():
    latest_articles = [story(slug, f"{slug}-daily-20260828") for slug in SLUGS]
    latest = {"date": "2026-08-28", "articles": latest_articles}
    desk = {"desks": {slug: [dict(article)] for slug, article in zip(SLUGS, latest_articles)}}
    return latest, desk


latest, desk = base()
result = audit(latest, desk, NOW)
assert result["status"] == "PASS", result

# Count depth must never hide a stale Manga/Anime desk.
latest, desk = base()
desk["desks"]["manga-anime"] = [story("manga-anime", f"anime-old-{i}-20260825") for i in range(5)]
result = audit(latest, desk, NOW)
assert result["status"] == "FAIL", result
assert any("manga-anime" in x for x in result["failures"]), result

# A current Daily story must propagate into its Rolling Desk even when another
# sufficiently recent Rolling story already exists.
latest, desk = base()
desk["desks"]["manchester-united"] = [story("manchester-united", "mu-other-20260828")]
result = audit(latest, desk, NOW)
assert result["status"] == "FAIL", result
assert any("current Daily" in x and "manchester-united" in x for x in result["failures"]), result

print("DESK_FRESHNESS_TESTS_OK")
