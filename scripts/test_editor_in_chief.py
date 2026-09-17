#!/usr/bin/env python3
from datetime import datetime, timezone
from editor_in_chief import audit
from semantic_copy_guard import semantic_copy_errors

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
        "sourceName": "Example",
        "sources": [{"name": "Example", "url": "https://example.com/story"}],
        "verifiedAt": "2026-08-27T05:00:00+08:00",
        "timeLabel": "2026年8月27日 05:00 HKT",
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
        {"checkedAt": "2026-08-26T21:30:00+00:00", "infrastructureMatch": True, "editorialFreshnessMatch": True,
         "liveMatch": True, "deskMatch": True, "stockMatch": True, "voiceManifestMatch": True},
        {"lastSearchAt": "2026-08-26T21:30:00+00:00"},
    )


args = base()
result = audit(*args, NOW)
assert result["status"] == "HEALTHY", result
assert result["repairPlan"] == [], result
assert result["policy"]["semanticCopyeditingGate"] is True, result
assert result["policy"]["todayFirstRecovery"] is True, result
assert result["policy"]["historicalBacklogNonBlocking"] is True, result
assert result["policy"]["outcomeBasedRecovery"] is True, result
assert result["policy"]["discordAlertIsNotPublicationProof"] is True, result
assert result["currentDay"]["recoveryMode"] == "TODAY_FIRST_NO_BACKFILL", result

args = list(base())
args[6] = {"lastSearchAt": "2026-08-26T20:00:00+00:00"}
result = audit(*args, NOW)
assert result["status"] == "AUTO_REPAIRING", result
assert any(x["workflow"] == "rolling-news-search.yml" for x in result["repairPlan"]), result

args = list(base())
args[5] = {"checkedAt": "2026-08-26T21:30:00+00:00", "infrastructureMatch": False, "editorialFreshnessMatch": True,
           "liveMatch": True, "deskMatch": True, "stockMatch": True, "voiceManifestMatch": True}
result = audit(*args, NOW)
assert any(x["workflow"] == "pages.yml" for x in result["repairPlan"]), result

args = list(base())
args[2]["desks"]["world"] = []
result = audit(*args, NOW)
assert any(f["code"] == "DESK_EMPTY" for f in result["findings"]), result
assert any(x["workflow"] == "rolling-news-search.yml" for x in result["repairPlan"]), result

args = list(base())
args[5] = {"checkedAt": "2026-08-26T21:30:00+00:00", "infrastructureMatch": True, "editorialFreshnessMatch": False,
           "liveMatch": True, "deskMatch": True, "stockMatch": True, "voiceManifestMatch": True}
result = audit(*args, NOW)
assert result["status"] == "HEALTHY_WITH_WARNINGS", result
assert any(f["code"] == "PUBLIC_EDITORIAL_STALE" for f in result["findings"]), result

args = list(base())
args[6] = {"lastSearchAt": "2026-08-26T20:00:00+00:00"}
previous = {"findings": [{"code": "COLLECTION_STALE", "severity": "critical"}]}
result = audit(*args, NOW, previous)
assert result["status"] == "RECOVERY_ESCALATION_REQUIRED", result
assert any(f["code"] == "PERSISTENT_COLLECTION_STALE" for f in result["findings"]), result
assert result["summary"]["persistentCriticalCount"] >= 1, result

# TODAY-FIRST Daily recovery: stale Daily must have an explicit production owner,
# and the message must demand today's edition directly rather than backfill.
day_now = datetime(2026, 8, 27, 2, 30, tzinfo=UTC)  # 10:30 HKT
args = list(base())
args[0] = {"date": "2026-08-25"}
result = audit(*args, day_now)
daily = [f for f in result["findings"] if f["code"] == "DAILY_STALE"]
assert daily and daily[0]["repair"] == "daily", result
assert "TODAY" in daily[0]["message"], result
plan = [x for x in result["repairPlan"] if x["area"] == "daily"]
assert plan and plan[0]["owner"] == "automation:Daily Priority Briefing", result
assert plan[0]["workflow"] is None, result

# Public propagation is outcome evidence: fresh repository data with stale public
# Live/Desk must remain a hard production failure even if infrastructure is healthy.
args = list(base())
args[5] = {"checkedAt": "2026-08-26T21:30:00+00:00", "infrastructureMatch": True,
           "editorialFreshnessMatch": True, "liveMatch": False, "deskMatch": False,
           "stockMatch": True, "voiceManifestMatch": True}
result = audit(*args, NOW)
assert any(f["code"] == "PUBLIC_LIVE_NOT_PROPAGATED" for f in result["findings"]), result
assert any(f["code"] == "PUBLIC_DESK_NOT_PROPAGATED" for f in result["findings"]), result
assert any(f["code"] == "DISCORD_PUBLICATION_TRUTH_GAP" for f in result["findings"]), result
assert any(x["workflow"] == "pages.yml" for x in result["repairPlan"]), result

# A stale Football story intentionally routed to a regional page is no longer a
# harmless duplicate warning. It is a repairable retention defect.
args = list(base())
old = story("football", "football-jleague-example-20260824")
old["title"] = "舊J-League跨版新聞"
old["deskSlugs"] = ["japan", "football"]
old["verifiedAt"] = "2026-08-24T05:00:00+08:00"
args[2]["desks"]["japan"].append(dict(old))
args[2]["desks"]["football"].append(dict(old))
result = audit(*args, NOW)
assert result["status"] == "AUTO_REPAIRING", result
assert any(f["code"] == "STALE_CROSS_DESK_FOOTBALL" and f["area"] == "japan" for f in result["findings"]), result
assert any(x["workflow"] == "merge-live-into-desk.yml" for x in result["repairPlan"]), result

# Regression: the corruption that escaped the old audit must now be a hard
# semantic-copyediting failure, not qualityErrorCount=0.
corrupt = story("hong-kong", "hk-dow-jones-journalists-association-regression")
corrupt["title"] = "道瓊斯指數 鍾斯阻鄭嘉如參選記協主席罪成　解僱相關控罪不成立"
corrupt["summary"] = "案件涉及《華爾街日報》僱主與香港記者協會主席鄭嘉如之間的僱傭爭議。"
corrupt["body"] = "《華爾街日報》母公司 Dow Jones Publishing 涉及一宗僱傭及解僱案件。" * 8
corrupt["sourceName"] = "Wall Street Journal / court reporting"
assert semantic_copy_errors(corrupt), "corrupt Dow Jones headline must be rejected"
args = list(base())
args[2]["desks"]["hong-kong"] = [corrupt]
result = audit(*args, NOW)
assert result["status"] == "EDITORIAL_ATTENTION_REQUIRED", result
assert result["deskAudit"]["hong-kong"]["semanticCopyErrorCount"] >= 1, result
assert any(f["code"] == "SEMANTIC_COPY_CORRUPTION" and f["area"] == "hong-kong" for f in result["findings"]), result

normal = story("market-economy", "market-dow-jones-normal")
normal["title"] = "道瓊斯工業平均指數升逾200點　市場等待通脹數據"
normal["summary"] = "美股主要指數上升，投資者等待最新通脹數據。"
normal["body"] = "美國股市上升，道瓊斯工業平均指數錄得升幅，市場關注利率前景。" * 8
assert semantic_copy_errors(normal) == [], semantic_copy_errors(normal)

print("EDITOR_IN_CHIEF_TESTS_OK")