#!/usr/bin/env python3
"""One-event fail-closed recovery for the current World desk.

Uses a genuinely current Reuters report and its real publication time.
It never retimestamps stale content: after the 8-hour World SLA the script
becomes a no-op and lets freshness validation fail closed.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T12:03:34+08:00")
MAX_AGE = dt.timedelta(hours=8)

STORY = {
    "id": "world-us-exim-africell-network-financing-20260911",
    "desk": "world",
    "deskSlugs": ["world"],
    "section": "國際｜非洲電訊",
    "sectionLabel": "世界",
    "status": "LATEST",
    "title": "美國擬向Africell提供近1億美元貸款　推動非華為網絡設備",
    "dek": "美國政府計劃透過進出口銀行向非洲電訊商Africell提供近1億美元貸款，資金將用於採購美國及盟友供應商的流動網絡技術。",
    "summary": "路透社9月11日引述知情人士及擬發布文件報道，美國進出口銀行計劃向Africell提供接近1億美元貸款，支持其在非洲市場升級流動網絡；華盛頓正推動更多可信賴、非華為設備進入海外電訊基建。",
    "body": "美國政府計劃透過美國進出口銀行向Africell提供接近1億美元貸款。路透社引述知情人士及一份擬發布新聞稿報道，這筆融資將協助Africell採購美國及盟友供應商的最新流動網絡技術，以擴充其非洲市場的通訊基建。\n\nAfricell在安哥拉、剛果民主共和國、岡比亞及塞拉利昂營運流動網絡。今次融資亦反映華盛頓持續以出口信貸及科技政策，推動美國與盟友設備供應商在非洲電訊市場擴大角色，降低當地網絡對華為設備的依賴。",
    "context": "美國近年把通訊基建、雲端及人工智能技術出口視為經濟與國家安全政策的一部分；Africell則是非洲少數具美國背景的大型流動網絡營運商。",
    "why": "近1億美元官方出口信貸若落實，會直接影響非洲流動網絡投資及設備供應格局，也反映美中科技競爭繼續延伸至非洲關鍵基建市場。",
    "watchNext": "留意美國進出口銀行正式公布的貸款條款、Africell實際採購哪些設備，以及相關投資會否擴展至更多非洲市場。",
    "sourceName": "Reuters / Africell",
    "sourceUrl": "https://www.reuters.com/world/china/trump-administration-lend-100-million-africell-countering-huawei-africa-2026-09-11/",
    "publishedAt": "2026-09-11T12:03:34+08:00",
    "timeLabel": "9月11日12:03 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/world/china/trump-administration-lend-100-million-africell-countering-huawei-africa-2026-09-11/"},
        {"name": "Africell", "url": "https://www.africell.com/"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - PUBLISHED
    if age < dt.timedelta(0) or age > MAX_AGE:
        print(f"WORLD_CURRENT_RECOVERY_NOOP age_h={age.total_seconds()/3600:.2f}")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    desks = data.get("desks")
    if not isinstance(desks, dict):
        raise SystemExit("desk-latest desks missing/invalid")
    if not isinstance(desks.get("world"), list):
        raise SystemExit("world desk missing/invalid")

    stories = desks["world"]
    if any(isinstance(s, dict) and s.get("id") == STORY["id"] for s in stories):
        print("WORLD_CURRENT_RECOVERY_NOOP already-present")
        return 0

    stories.insert(0, dict(STORY))
    PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"WORLD_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
