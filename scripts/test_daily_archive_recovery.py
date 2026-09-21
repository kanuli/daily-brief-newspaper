#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import build_today_daily_from_desk as daily_builder
from build_today_daily_from_desk import daily_candidate
from sync_daily_archive import sync


def story(ident: str = "world-test") -> dict:
    body = (
        "這是一段用於回歸測試的新聞內文，內容足夠完整，包含事件背景、已核實事實及相關公共影響，避免任何編輯流程文字。"
        "同時保留足夠長度，以符合日報公開稿件的最低內容要求。\n\n"
        "第二段補充事件後續、資料來源與需要繼續觀察的發展，確保公開稿件不是簡短佔位內容，而是可以獨立閱讀的新聞摘要。"
        "這些句子只用於測試資料結構與驗證閘門。"
    )
    return {
        "id": ident,
        "desk": "world",
        "title": "測試國際新聞標題",
        "dek": "測試新聞導語，交代事件核心內容與最新發展。",
        "summary": "測試摘要說明事件、影響以及目前已核實的重要資料。",
        "body": body,
        "context": "背景資料說明事件發展脈絡及相關制度環境。",
        "why": "事件可能影響公共政策與國際關係，因此值得持續留意。",
        "watchNext": "留意官方後續公布、政策變化以及各方正式回應。",
        "sourceName": "Example News",
        "sourceUrl": "https://example.com/news",
        "timeLabel": "2026年9月21日 09:00 HKT",
        "verifiedAt": "2026-09-21T09:00:00+08:00",
        "sources": [{"name": "Example News", "url": "https://example.com/news"}],
    }


valid, error = daily_candidate(story())
assert valid is not None and error is None, error

bad = story("world-bad")
bad["summary"] = "本輪檢查後加入的內部流程文字不應出現在公開新聞。"
valid, error = daily_candidate(bad)
assert valid is None, valid
assert error and "本輪" in error, error

# Before 08:00 HKT, recovery must retain yesterday without even requiring a
# current desk file. Overnight Live/Desk remains the freshness layer.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    data = root / "data"
    data.mkdir()
    (data / "latest.json").write_text(json.dumps({"date": "2026-09-20"}), encoding="utf-8")
    old_data = daily_builder.DATA
    daily_builder.DATA = data
    try:
        _daily, meta = daily_builder.build(datetime(2026, 9, 20, 21, 0, tzinfo=timezone.utc))  # 05:00 HKT Sep 21
        assert meta["changed"] is False and meta["reason"] == "before-daily-window", meta
    finally:
        daily_builder.DATA = old_data

# Archive recovery: only a valid dated JSON may create an archive row/wrapper.
with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    data = root / "data"
    editions = root / "editions"
    data.mkdir()
    editions.mkdir()
    sample = story()
    daily = {
        "date": "2026-09-21",
        "editorialStandardVersion": 3,
        "contentVersion": 3,
        "leadId": sample["id"],
        "topFive": [sample["id"]],
        "articles": [sample],
        "sections": [{"slug": "world", "title": "世界", "subtitle": "國際", "articleIds": [sample["id"]]}],
    }
    (data / "2026-09-21.json").write_text(json.dumps(daily, ensure_ascii=False), encoding="utf-8")
    template = '<!doctype html><html><head><title>2026-09-14｜每日晨報 Daily Brief</title></head><body data-edition="2026-09-14"><span data-edition-date>2026-09-14</span><script src="assets/js/newspaper.js?v=2026-09-14"></script></body></html>'
    (editions / "2026-09-14.html").write_text(template, encoding="utf-8")
    result = sync(root)
    archive = json.loads((data / "archive.json").read_text(encoding="utf-8"))
    assert result["newestDate"] == "2026-09-21", result
    assert archive["editions"][0]["date"] == "2026-09-21", archive
    wrapper = editions / "2026-09-21.html"
    assert wrapper.is_file(), result
    text = wrapper.read_text(encoding="utf-8")
    assert 'data-edition="2026-09-21"' in text and "2026-09-14" not in text, text

print("DAILY_ARCHIVE_RECOVERY_TESTS_OK")
