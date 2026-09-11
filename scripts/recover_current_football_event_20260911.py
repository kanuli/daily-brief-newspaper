#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Football desk.

Uses a genuinely current Reuters match report and its real publication time.
It never retimestamps stale content: after the 8-hour Football SLA the script
becomes a no-op and lets freshness validation fail closed.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
PUBLISHED = dt.datetime.fromisoformat("2026-09-12T05:38:00+08:00")
MAX_AGE = dt.timedelta(hours=8)

STORY = {
    "id": "football-rennes-marseille-thomasson-ligue1-20260912",
    "desk": "football",
    "deskSlugs": ["football"],
    "section": "足球｜法甲",
    "sectionLabel": "足球",
    "status": "LATEST",
    "title": "湯馬臣一箭定江山　雷恩1比0挫馬賽暫登法甲榜首",
    "dek": "Adrien Thomasson下半場攻入全場唯一入球，雷恩主場1比0擊敗馬賽，四戰累積10分暫升法甲榜首；馬賽則吞下三連敗。",
    "summary": "Reuters報道，雷恩憑Adrien Thomasson第52分鐘入球，主場1比0擊敗馬賽，四戰取得10分並暫時升上法甲榜首。馬賽開季首輪大勝後連輸三場，聯賽形勢迅速轉差。",
    "body": "雷恩周五在法甲主場1比0擊敗馬賽。上半場雙方未能打破僵局，到第52分鐘，後備上陣的Mousa Tamari把球頂回門前，Adrien Thomasson把握機會射入，取得他加盟雷恩後首個入球。\n\nThomasson其後曾射中橫楣，未能擴大比數，但雷恩仍守住勝果。球隊四戰累積10分，暫時以一分領先少賽一場的摩納哥升上榜首。馬賽則在開季4比0大勝斯特拉斯堡後，接連不敵摩納哥、巴黎FC及雷恩，三連敗後只得3分。",
    "context": "法甲開季前列形勢仍未定型，摩納哥、巴黎聖日耳門等球隊仍有機會在本輪後改寫排名；雷恩今仗先把壓力交給其他爭標隊伍。",
    "why": "雷恩暫登榜首及馬賽三連敗同時改變法甲早段走勢，後者的低迷亦會加大教練與陣容調整壓力。",
    "watchNext": "留意摩納哥周六作客斯特拉斯堡，以及巴黎聖日耳門周日作客比斯特的結果；馬賽下一輪能否止住連敗亦是焦點。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/sports/soccer/thomasson-target-as-renne-beat-marseille-go-top-ligue-1-2026-09-11/",
    "publishedAt": "2026-09-12T05:38:00+08:00",
    "timeLabel": "9月12日05:38 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/thomasson-target-as-renne-beat-marseille-go-top-ligue-1-2026-09-11/"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - PUBLISHED
    if age < dt.timedelta(0) or age > MAX_AGE:
        print(f"FOOTBALL_CURRENT_RECOVERY_NOOP age_h={age.total_seconds()/3600:.2f}")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    desks = data.get("desks")
    if not isinstance(desks, dict):
        raise SystemExit("desk-latest desks missing/invalid")
    if not isinstance(desks.get("football"), list):
        raise SystemExit("football desk missing/invalid")

    stories = desks["football"]
    if any(isinstance(s, dict) and s.get("id") == STORY["id"] for s in stories):
        print("FOOTBALL_CURRENT_RECOVERY_NOOP already-present")
        return 0

    stories.insert(0, dict(STORY))
    PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"FOOTBALL_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
