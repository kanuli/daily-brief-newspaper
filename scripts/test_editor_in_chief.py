#!/usr/bin/env python3
from datetime import datetime, timezone
from editor_in_chief import audit

UTC = timezone.utc
NOW = datetime(2026, 8, 26, 21, 35, tzinfo=UTC)  # 05:35 HKT, outside normal Live/Stock window


def story(slug, ident):
    return {
        "id": ident,
        "desk": slug,
        "title": f"{slug} 測試新聞標題",
        "summary": "這是一段足夠長度的測試摘要，用來驗證新聞稿基本結構。",
        "body": "這是一段足夠長度的測試新聞內文。" * 8,
        "sourceUrl": "https://example.com/story",
        "sources": [{"name": "Example", "url": "https://example.com/story"}],
    }


def base():
    desks = {
        s: [story(s, f"{s}-20260827-0500")]
        for s in (
            "world", "asia", "hong-kong", "japan", "market-economy",
            "ai-tech", "manga-anime", "manchester-united", "football",
        )
    }
    return (
        {"date": "2026-08-27"},
        {"lastUpdated": "2026-08-26T21:00:00+00:00"},
        {"desks": desks},
        {"generatedAt": "2026-08-26T20:52:00+00:00", "lastCheckedAt": "2026-08-26T21:05:00+00:00", "collectionStatus": "COMPLETE"},
        {"engine": "typangaa/canto-tts-nano", "availableArticleCount": 10, "generatedAt": "2026-08-26T21:00:00+00:00", "pendingArticleCount": 0},
        {"checkedAt": "2026-08-26T21:30:00+00:00", "infrastructureMatch": True, "editorialFreshnessMatch": True},
        {"lastSearchAt": "2026-08-26T21:30:00+00:00"},
    )


args = base()
result = audit(*args, NOW)
assert result["status"] == "HEALTHY", result
assert result["repairPlan"] == [], result

args = list(base())
args[6] = {"lastSearchAt": "2026-08-26T20:00:00+00:00"}
result = audit(*args, NOW)
assert result["status"] == "AUTO_REPAIRING", result
assert any(x["workflow"] == "rolling-news-search.yml" for x in result["repairPlan"]), result

args = list(base())
args[5] = {"checkedAt": "2026-08-26T21:30:00+00:00", "infrastructureMatch": False, "editorialFreshnessMatch": True}
result = audit(*args, NOW)
assert any(x["workflow"] == "pages.yml" for x in result["repairPlan"]), result

args = list(base())
args[2]["desks"]["world"] = []
result = audit(*args, NOW)
assert any(f["code"] == "DESK_EMPTY" for f in result["findings"]), result
assert any(x["workflow"] == "rolling-news-search.yml" for x in result["repairPlan"]), result

args = list(base())
args[5] = {"checkedAt": "2026-08-26T21:30:00+00:00", "infrastructureMatch": True, "editorialFreshnessMatch": False}
result = audit(*args, NOW)
assert result["status"] == "HEALTHY_WITH_WARNINGS", result
assert any(f["code"] == "PUBLIC_EDITORIAL_STALE" for f in result["findings"]), result

args = list(base())
args[6] = {"lastSearchAt": "2026-08-26T20:00:00+00:00"}
previous = {"findings": [{"code": "COLLECTION_STALE", "severity": "critical"}]}
result = audit(*args, NOW, previous)
assert result["status"] == "EDITORIAL_ATTENTION_REQUIRED", result
assert any(f["code"] == "PERSISTENT_COLLECTION_STALE" for f in result["findings"]), result

print("EDITOR_IN_CHIEF_TESTS_OK")
