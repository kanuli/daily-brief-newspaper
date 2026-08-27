#!/usr/bin/env python3
from datetime import datetime, timezone

from desk_retention import expired_cross_desk_football, keep_on_desk, story_time


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def assert_false(value, message):
    if value:
        raise AssertionError(message)


def main():
    now = datetime.fromisoformat("2026-08-27T04:10:00+00:00")  # 12:10 HKT

    jleague = {
        "id": "football-jleague-machida-20260825",
        "desk": "football",
        "deskSlugs": ["japan", "football"],
        "title": "J-League sample",
    }
    hkpl = {
        "id": "football-hkpl-shatin-20260825",
        "desk": "football",
        "deskSlugs": ["hong-kong", "football"],
        "title": "HKPL sample",
    }
    fresh = {
        "id": "football-jleague-fresh-20260827-1100",
        "desk": "football",
        "deskSlugs": ["japan", "football"],
        "title": "Fresh J-League sample",
    }
    ai_cross = {
        "id": "ai-nvidia-q2-results-20260825",
        "desk": "ai-tech",
        "deskSlugs": ["ai-tech", "market-economy"],
        "title": "AI sample",
    }

    assert_true(story_time(jleague, now=now) is not None, "date-only football ID must be parseable")
    assert_true(expired_cross_desk_football(jleague, "japan", now=now), "old J-League cross-post must expire from Japan")
    assert_true(expired_cross_desk_football(hkpl, "hong-kong", now=now), "old HKPL cross-post must expire from Hong Kong")
    assert_false(expired_cross_desk_football(jleague, "football", now=now), "story must remain on Football desk")
    assert_false(expired_cross_desk_football(fresh, "japan", now=now), "fresh football cross-post may remain on Japan")
    assert_false(expired_cross_desk_football(ai_cross, "market-economy", now=now), "non-football multi-desk routing must not be affected")
    assert_false(keep_on_desk(jleague, "japan", now=now), "expired Japan cross-post must be filtered")
    assert_true(keep_on_desk(jleague, "football", now=now), "Football canonical copy must be retained")

    print("DESK_RETENTION_TEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
