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
    return {
        "id": ident, "desk": desk_name, "title": title,
        "url": f"https://news.example/{ident}", "source": "Example News",
        "provider": "Test RSS", "query": f"{desk_name} when:8h",
        "publishedAt": "2026-09-28T03:30:00Z",
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
    assert "\n\n" in article["body"]
    assert len(re.findall(r"[\u3400-\u9fff]", article["body"])) >= 95

desk["desks"]["japan"].insert(0, {"id": "existing", "title": "existing", "publishedAt": "2026-09-27T01:00:00Z", "sourceUrl": "https://news.example/jp-1"})
deduped = produce(staging, desk, live, NOW)
assert "japan" in deduped["coverage"]["skippedDesks"], deduped

staging["desks"]["football"][0]["publishedAt"] = "2026-09-29T03:30:00Z"
future = produce(staging, desk, live, NOW)
assert "football" in future["coverage"]["skippedDesks"], future

print("GENERAL_NEWS_PRODUCER_TESTS_OK")
