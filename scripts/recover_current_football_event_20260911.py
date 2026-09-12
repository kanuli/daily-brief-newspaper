#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Football desk.

Uses a genuinely current Reuters football report and its real publication time.
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
PUBLISHED = dt.datetime.fromisoformat("2026-09-12T19:38:00+08:00")
MAX_AGE = dt.timedelta(hours=8)

STORY = {
    "id": "football-dr-congo-world-cup-recruitment-20260912",
    "desk": "football",
    "deskSlugs": ["football"],
    "section": "足球｜國際賽",
    "sectionLabel": "足球",
    "status": "LATEST",
    "title": "剛果（金）世盃突破帶動招兵　六名歐洲球員加入非國盃外圍賽名單",
    "dek": "剛果（金）今年世盃打入32強後擴大國家隊人才庫，教練Desabre新召六名效力歐洲球會的球員，包括前曼聯中堅Willy Kambwala。",
    "summary": "Reuters報道，剛果（金）今年首次突破世盃分組賽後，吸引更多具剛果血統的歐洲出生球員加入。球隊本月非洲國家盃外圍賽名單新增六名歐洲球會球員，部分人仍需FIFA批准轉換代表資格。",
    "body": "剛果（金）在今年世界盃打入32強後，正加快擴大國家隊人才庫。Reuters報道，教練Sebastien Desabre為9月24日主場對赤道幾內亞及四日後作客津巴布韋的2027非洲國家盃外圍賽，新召六名效力歐洲球會的球員。\n\n名單包括前曼聯中堅、現效力Como的Willy Kambwala，以及Ezechiel Banzuzi、Stanis Idumbo、Jordy Makengo、Noah Mbamba和Kevin Pedro。當中部分球員曾代表荷蘭、比利時或法國青年隊，需要取得FIFA批准才能正式轉換代表資格。Desabre亦計劃在10月對烏干達的友賽再考察更多具剛果血統的歐洲球員。",
    "context": "剛果（金）今年在北美世界盃首次突破分組賽，32強對英格蘭一度接近爆冷。成績提升令國家隊對海外雙重國籍球員的吸引力增加。",
    "why": "國家隊賽事的成功正直接改變球員代表資格選擇，剛果（金）若能吸納更多歐洲聯賽球員，將提高2027非洲國家盃及其後國際賽競爭力。",
    "watchNext": "留意FIFA是否批准相關球員轉換代表資格、9月兩場非國盃外圍賽名單，以及10月友賽會否再有更多歐洲出生球員加入。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/sports/soccer/dr-congos-world-cup-exploits-encourage-more-players-join-their-cause-2026-09-12/",
    "publishedAt": "2026-09-12T19:38:00+08:00",
    "timeLabel": "9月12日19:38 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/dr-congos-world-cup-exploits-encourage-more-players-join-their-cause-2026-09-12/"}
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
