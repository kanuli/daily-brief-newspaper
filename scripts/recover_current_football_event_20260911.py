#!/usr/bin/env python3
"""One-event fail-closed recovery for current Manchester United/Football desks.

Uses a genuinely current Reuters report and its real publication time.
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
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T11:08:00+08:00")
MAX_AGE = dt.timedelta(hours=8)

STORY = {
    "id": "manchester-united-sesko-city-derby-return-form-20260911",
    "desk": "manchester-united",
    "deskSlugs": ["manchester-united", "football"],
    "section": "Manchester United｜曼市打吡",
    "sectionLabel": "Manchester United",
    "status": "LATEST",
    "title": "錫斯高連續兩仗入球　卡域克稱復勇為曼市打吡添助力",
    "dek": "曼聯前鋒Benjamin Sesko傷癒後連續兩仗建功，領隊Michael Carrick指其速度、體格及衝擊防線能力，為周日對曼城前的重要增益。",
    "summary": "路透社9月11日報道，Benjamin Sesko傷癒復出後先在英超對愛華頓後備入球，再於歐聯4比0擊敗Sabah一役建功；Michael Carrick表示，球員逐步恢復比賽狀態，對周日曼市打吡是正面消息。",
    "body": "曼聯前鋒Benjamin Sesko在脛骨傷勢休戰近三個月後，近兩場比賽連續取得入球。路透社報道，他先在英超作客2比2賽和愛華頓一役後備上陣並於末段破門，其後在周四歐聯主場4比0擊敗Sabah時再度建功。\n\n領隊Michael Carrick表示，Sesko的體格、速度及在最後一線衝擊對手防線的能力，是目前陣容的重要選項。曼聯下一場將於周日主場迎戰曼城，Sesko亦表示兩場入球提升信心，當前重點是恢復體能並準備打吡。",
    "context": "曼聯在歐聯大勝Sabah後轉回英超賽程，周日曼市打吡是球隊近期最重要的本土賽事之一。Sesko剛從長期傷患回歸，出場時間仍受到管理。",
    "why": "主力前鋒傷癒後連續入球，直接影響曼聯對曼城時的正選、後備及進攻部署；Carrick公開確認其狀態回升，具有即時賽前新聞價值。",
    "watchNext": "留意Carrick在曼市打吡前的傷兵及正選更新、Sesko能否首次傷癒後踢足更多時間，以及曼聯如何在歐聯後調整前場輪換。",
    "sourceName": "Reuters / Manchester United",
    "sourceUrl": "https://www.reuters.com/sports/soccer/man-uniteds-carrick-pleased-with-seskos-return-form-ahead-city-derby-2026-09-11/",
    "publishedAt": "2026-09-11T11:08:00+08:00",
    "timeLabel": "9月11日11:08 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/man-uniteds-carrick-pleased-with-seskos-return-form-ahead-city-derby-2026-09-11/"},
        {"name": "Manchester United", "url": "https://www.manutd.com/en"}
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
    for slug in ("manchester-united", "football"):
        if not isinstance(desks.get(slug), list):
            raise SystemExit(f"{slug} desk missing/invalid")

    changed = False
    for slug in ("manchester-united", "football"):
        stories = desks[slug]
        if not any(isinstance(s, dict) and s.get("id") == STORY["id"] for s in stories):
            stories.insert(0, dict(STORY))
            changed = True

    if changed:
        PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"FOOTBALL_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    else:
        print("FOOTBALL_CURRENT_RECOVERY_NOOP already-present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
