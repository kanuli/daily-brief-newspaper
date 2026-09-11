#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Japan desk.

Uses a genuinely current Reuters report and its real publication time.
It never retimestamps stale content: after the 12-hour Japan SLA the script
becomes a no-op and lets freshness validation fail closed.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T15:47:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "japan-kioxia-us-listing-ai-investor-spotlight-20260911",
    "desk": "japan",
    "deskSlugs": ["japan"],
    "section": "日本｜產業",
    "sectionLabel": "日本",
    "status": "LATEST",
    "title": "鎧俠擬赴美掛牌　大型AI基金經理：可提升日本晶片股全球能見度",
    "dek": "日本記憶體晶片商鎧俠準備以美國存託股份形式赴美上市；Voya旗下AI基金經理認為，美國市場較高流動性有助日本科技企業接觸全球投資者。",
    "summary": "日本記憶體晶片商鎧俠正準備在美國發行存託股份。Voya Investments一名管理140億美元AI主題基金的投資經理表示，美國上市可改善流動性，令日本半導體企業更容易進入全球大型基金的投資視野。",
    "body": "日本記憶體晶片商鎧俠正準備在美國發行存託股份，以擴大投資者基礎。Reuters報道，Voya Investments一名管理140億美元AI主題基金的投資經理表示，鎧俠若能在美國市場交易，可改善股份流動性，並提高日本科技企業在全球投資者之間的能見度。\n\n鎧俠今年股價升幅在日經225指數成分股中居前，公司早在5月已表示正為美國上市作準備。該基金經理指出，日本供應鏈內有不少具吸引力的企業，但大型海外基金能否建立足夠規模持倉，往往取決於流動性；美國掛牌可能降低這項門檻。",
    "context": "日本半導體與記憶體企業近年受惠於AI基建需求，但海外大型機構投資者仍會衡量本地市場流動性及交易便利程度。",
    "why": "鎧俠若成功建立美國交易渠道，不只是單一公司的融資安排，也可能影響海外資金配置日本半導體供應鏈的方式。",
    "watchNext": "留意鎧俠正式提交美國上市文件、ADS規模與時間表，以及其他日本科技企業會否跟隨採取跨市場上市策略。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/world/asia-pacific/us-listing-could-put-japans-kioxia-global-ai-spotlight-voyas-thomas-says-2026-09-11/",
    "publishedAt": "2026-09-11T15:47:00+08:00",
    "timeLabel": "9月11日15:47 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/world/asia-pacific/us-listing-could-put-japans-kioxia-global-ai-spotlight-voyas-thomas-says-2026-09-11/"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - PUBLISHED
    if age < dt.timedelta(0) or age > MAX_AGE:
        print(f"JAPAN_CURRENT_RECOVERY_NOOP age_h={age.total_seconds()/3600:.2f}")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    desks = data.get("desks")
    if not isinstance(desks, dict):
        raise SystemExit("desk-latest desks missing/invalid")
    if not isinstance(desks.get("japan"), list):
        raise SystemExit("japan desk missing/invalid")

    stories = desks["japan"]
    if any(isinstance(s, dict) and s.get("id") == STORY["id"] for s in stories):
        print("JAPAN_CURRENT_RECOVERY_NOOP already-present")
        return 0

    stories.insert(0, dict(STORY))
    PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"JAPAN_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
