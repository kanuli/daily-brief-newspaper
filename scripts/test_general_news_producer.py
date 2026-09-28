#!/usr/bin/env python3
import re
from datetime import datetime, timezone

from general_news_verified_producer import produce

NOW = datetime(2026, 9, 28, 4, 30, tzinfo=timezone.utc)


def story(desk, stamp):
    return {"id": f"old-{desk}", "desk": desk, "title": f"old {desk}", "publishedAt": stamp, "sourceUrl": f"https://old/{desk}"}


desk = {"desks": {
    "world": [story("world", "2026-09-28T01:00:00Z")],
    "asia": [story("asia", "2026-09-28T01:00:00Z")],
    "hong-kong": [story("hong-kong", "2026-09-27T01:00:00Z")],
    "japan": [story("japan", "2026-09-27T01:00:00Z")],
    "market-economy": [story("market-economy", "2026-09-28T01:00:00Z")],
    "ai-tech": [story("ai-tech", "2026-09-28T01:00:00Z")],
    "manga-anime": [story("manga-anime", "2026-09-27T01:00:00Z")],
    "manchester-united": [story("manchester-united", "2026-09-27T01:00:00Z")],
    "football": [story("football", "2026-09-27T01:00:00Z")],
}}


def candidate(desk_name, title, ident):
    body = (
        "測試來源公布一項與所屬新聞版面直接相關的新進展，交代事件的主要參與者、已確認行動及公布時間。"
        "編輯核對來源頁面後，以香港繁體中文整理重點，並保留原始連結供讀者查閱。\n\n"
        "第二段補充事件背景、目前已知影響及下一個可核實節點；內容只採用來源正文及附帶證據，"
        "不會用空泛流程說明代替新聞事實，亦不會把外語標題直接當作中文報道發布。"
    )
    return {
        "id": ident, "desk": desk_name, "title": title,
        "url": f"https://news.example/{ident}", "source": "Example News",
        "provider": "Test RSS", "query": f"{desk_name} when:8h",
        "publishedAt": "2026-09-28T03:30:00Z",
        "sourceEvidence": [{"name": "Example News", "url": f"https://news.example/{ident}"}],
        "verifiedCopy": {
            "title": "測試新聞來源公布具體新進展並交代後續安排",
            "dek": "來源正文確認事件內容、相關參與者及公布時間，報道以香港繁體中文整理。",
            "summary": "這是一則有來源正文支持的具體新聞摘要，並非只重複外語標題或編採流程。",
            "body": body,
            "context": "事件與相應新聞版面直接相關，來源證據已包含正文層面的具體資料。",
            "why": "新進展會影響相關讀者對事件現況及下一步安排的理解。",
            "watchNext": "留意發布機構及當事人其後公布的執行時間、結果或正式修訂。",
        },
    }


staging = {"lastSearchAt": "2026-09-28T04:15:00Z", "desks": {
    "hong-kong": [candidate("hong-kong", "香港今日有可核實的新消息並已由來源發布 - Example News", "hk-1")],
    "japan": [candidate("japan", "Japan company announces a substantial new technology programme - Example News", "jp-1")],
    "manga-anime": [candidate("manga-anime", "New anime project publishes its official production update - Example News", "anime-1")],
    "manchester-united": [candidate("manchester-united", "Manchester United publish a first-team injury update - Example News", "mu-1")],
    "football": [candidate("football", "UEFA publishes the latest international fixture update - Example News", "fb-1")],
}}
live = {"lastUpdated": "2026-09-28T12:00:00+08:00", "items": []}

result = produce(staging, desk, live, NOW)
assert result["status"] == "VERIFIED_DRAFT", result
assert len(result["articles"]) == 5, result
assert set(result["coverage"]["staleDesks"]) == {"hong-kong", "japan", "manga-anime", "manchester-united", "football"}
assert result["targetPublication"] == "2026-09-28T12:21:00+08:00", result
for article in result["articles"]:
    assert article["sourceName"] == "Example News"
    assert article["sourceUrl"].startswith("https://news.example/")
    assert article["verification"]["noUnsupportedDetail"] is True
    assert article["verification"]["cantoneseCopyVerified"] is True
    assert "\n\n" in article["body"]
    assert len(re.findall(r"[\u3400-\u9fff]", article["body"])) >= 95

desk["desks"]["japan"].insert(0, {"id": "existing", "title": "existing", "publishedAt": "2026-09-27T01:00:00Z", "sourceUrl": "https://news.example/jp-1"})
deduped = produce(staging, desk, live, NOW)
assert "japan" in deduped["coverage"]["skippedDesks"], deduped

staging["desks"]["football"][0]["publishedAt"] = "2026-09-29T03:30:00Z"
future = produce(staging, desk, live, NOW)
assert "football" in future["coverage"]["skippedDesks"], future

staging["desks"]["manchester-united"][0].pop("verifiedCopy")
untranslated = produce(staging, desk, live, NOW)
assert "manchester-united" in untranslated["coverage"]["skippedDesks"], untranslated

print("GENERAL_NEWS_PRODUCER_TESTS_OK")
