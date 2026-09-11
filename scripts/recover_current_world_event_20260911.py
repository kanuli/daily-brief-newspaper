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
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T18:04:00+08:00")
MAX_AGE = dt.timedelta(hours=8)

STORY = {
    "id": "world-us-september-11-25th-anniversary-20260911",
    "desk": "world",
    "deskSlugs": ["world"],
    "section": "國際｜美國",
    "sectionLabel": "世界",
    "status": "LATEST",
    "title": "美國紀念九一一25周年　遇難者家屬再讀近3,000名死者姓名",
    "dek": "紐約、五角大樓及賓夕法尼亞州舉行紀念活動；紐約消防局表示，除當日殉職343名消防員外，已有逾600名消防員因相關疾病離世。",
    "summary": "九一一襲擊25周年，美國多地舉行悼念。紐約世貿中心遺址的儀式再次由遇難者家屬讀出死者姓名，並按當年客機撞擊及雙塔倒塌時刻默哀；紀念活動亦聚焦救援人員長期健康後遺症及事件對美國社會與外交政策的持續影響。",
    "body": "美國周五紀念九一一恐怖襲擊25周年。路透社報道，紐約世貿中心遺址、五角大樓及賓夕法尼亞州尚克斯維爾分別舉行活動，遇難者家屬在紐約儀式逐一讀出2,977名九一一死者，以及1993年世貿中心爆炸案6名死者的姓名，並在當年兩架客機撞擊雙塔及雙塔倒塌的時間默哀。\n\n紀念活動亦再次把焦點放在第一批救援人員的長期健康代價。紐約消防局在襲擊當日失去343名成員，其後已有逾600名曾參與救援的消防員因與九一一相關疾病死亡。事件同時深刻改變美國國土安全、反恐政策、海外軍事行動及社會對穆斯林社群的態度，25年後仍是美國公共生活的重要歷史分水嶺。",
    "context": "2001年9月11日，四架被劫持客機分別撞向紐約世貿中心、五角大樓及墜毀於賓夕法尼亞州，造成近3,000人死亡，並觸發其後長達多年的反恐戰爭及國土安全制度重整。",
    "why": "25周年不只是周年紀念，也重新呈現襲擊對救援人員健康、國家安全制度、外交政策及社會關係留下的長期影響。",
    "watchNext": "留意紐約、華盛頓及尚克斯維爾後續紀念活動，以及聯邦和地方政府對九一一相關疾病醫療與補償計劃的最新安排。",
    "sourceName": "Reuters / 9/11 Memorial & Museum",
    "sourceUrl": "https://www.reuters.com/world/us/americans-mark-25-years-since-september-11-attacks-amid-enduring-grief-2026-09-11/",
    "publishedAt": "2026-09-11T18:04:00+08:00",
    "timeLabel": "9月11日18:04 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/world/us/americans-mark-25-years-since-september-11-attacks-amid-enduring-grief-2026-09-11/"},
        {"name": "9/11 Memorial & Museum", "url": "https://www.911memorial.org/"}
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
