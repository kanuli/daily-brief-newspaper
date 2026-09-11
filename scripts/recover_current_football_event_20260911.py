#!/usr/bin/env python3
"""One-event fail-closed recovery for current Manchester United/Football desks.

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
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T03:25:00+08:00")
MAX_AGE = dt.timedelta(hours=8)

STORY = {
    "id": "manchester-united-sabah-4-0-champions-league-20260911",
    "desk": "manchester-united",
    "deskSlugs": ["manchester-united", "football"],
    "section": "Manchester United｜歐聯",
    "sectionLabel": "Manchester United",
    "status": "LATEST",
    "title": "曼聯4球大勝Sabah　重返歐聯首戰零封開門紅",
    "dek": "曼聯在奧脫福以4比0擊敗Sabah，古亞、般奴費南迪斯、錫斯高及利辛度馬天尼斯各建一功。",
    "summary": "曼聯相隔兩季重返歐聯後取得理想開局，主場4比0擊敗阿塞拜疆球會Sabah；四名不同球員入球，球隊亦保持清白之身。",
    "body": "曼聯在2026/27歐聯聯賽階段首戰主場以4比0擊敗Sabah。路透社報道，Matheus Cunha、Bruno Fernandes、Benjamin Sesko及Lisandro Martinez先後入球，令球隊在相隔兩季後重返歐聯即取得三分。\n\n大勝亦為曼聯在周日曼市打吡前建立正面勢頭。首輪同日拜仁慕尼黑以5比0擊敗Bodø/Glimt，而Como則在球會史上首次歐聯比賽以4比1大勝RB Leipzig，顯示首輪積分榜早段已出現多場大比分賽果。",
    "context": "曼聯今季重返歐洲最高級別球會賽事，首輪主場取勝兼零封，有助減輕聯賽階段早段搶分壓力。",
    "why": "歐聯新制要求各隊在單一聯賽階段累積積分，首輪三分及四球淨勝差均具實際排名價值；同時賽果會直接影響曼聯周末打吡前的輪換與體能部署。",
    "watchNext": "留意周日曼市打吡的輪換、傷兵及體能狀況，以及曼聯下一輪歐聯作客馬德里體育會的部署。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/sports/soccer/psv-held-by-shakhtar-fenerbahce-draw-with-roma-return-champions-league-2026-09-10/",
    "publishedAt": "2026-09-11T03:25:00+08:00",
    "timeLabel": "9月11日03:25 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/psv-held-by-shakhtar-fenerbahce-draw-with-roma-return-champions-league-2026-09-10/"},
        {"name": "Manchester United", "url": "https://www.manutd.com/en/matches/matchcenter/man-utd-vs-sabah-match-2727843"}
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
