#!/usr/bin/env python3
"""Regression tests for curated specialist/public-desk freshness recovery."""
from __future__ import annotations

import datetime as dt
import tempfile
from pathlib import Path

from recover_manga_freshness_watchdog import HKT, apply_recovery, atomic_write_json


def story(story_id: str, slug: str, published: str) -> dict:
    return {
        "id": story_id,
        "desk": slug,
        "deskSlugs": [slug],
        "title": "測試新聞標題",
        "dek": "這是一段足夠長度的測試副題，用來驗證復原流程。",
        "summary": "這是一段足夠長度的測試摘要，用來驗證復原流程不會偽造新鮮度。",
        "body": "這是一段測試正文。" * 20,
        "sourceUrl": "https://example.com/story",
        "publishedAt": published,
    }


def main() -> None:
    now = dt.datetime(2026, 9, 21, 18, 15, tzinfo=HKT)

    # 1. A stale curated candidate must not abort the whole recovery chain.
    data = {"desks": {"manga-anime": [story("old-desk", "manga-anime", "2026-09-18T00:00:00+08:00")]}}
    stale_pool = {
        "manga-anime": [story("expired-fallback", "manga-anime", "2026-09-18T01:00:00+08:00")]
    }
    changed, recovered = apply_recovery(data, now=now, recovery_pool=stale_pool)
    assert changed is False
    assert recovered == []
    assert data["desks"]["manga-anime"][0]["id"] == "old-desk"

    # 2. A current source-backed candidate must repair a stale desk.
    fresh_pool = {
        "manga-anime": [story("fresh-fallback", "manga-anime", "2026-09-21T12:00:00+08:00")]
    }
    changed, recovered = apply_recovery(data, now=now, recovery_pool=fresh_pool)
    assert changed is True
    assert recovered == ["manga-anime"]
    assert data["desks"]["manga-anime"][0]["id"] == "fresh-fallback"

    # 3. A desk already within SLA must never be replaced by emergency copy.
    current = {"desks": {"hong-kong": [story("normal-current", "hong-kong", "2026-09-21T17:00:00+08:00")]}}
    hk_pool = {"hong-kong": [story("emergency", "hong-kong", "2026-09-21T16:00:00+08:00")]}
    changed, recovered = apply_recovery(current, now=now, recovery_pool=hk_pool)
    assert changed is False
    assert recovered == []
    assert current["desks"]["hong-kong"][0]["id"] == "normal-current"

    # 4. Atomic writer must leave a parseable non-empty JSON object on disk.
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "desk.json"
        atomic_write_json(path, data)
        text = path.read_text(encoding="utf-8")
        assert text.strip().startswith("{")
        assert "fresh-fallback" in text

    print("SPECIALIST_FRESHNESS_RECOVERY_TESTS_OK")


if __name__ == "__main__":
    main()
