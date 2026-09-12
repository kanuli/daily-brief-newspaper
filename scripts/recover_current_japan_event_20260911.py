#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Japan desk.

Uses a current, primary-source Japanese government statement. The source page
provides a publication date but no precise clock time, so the story preserves
that date and uses the actual editorial verification time for freshness rather
than inventing a source publication timestamp.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
VERIFIED = dt.datetime.fromisoformat("2026-09-12T20:20:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "japan-mofa-houthi-saudi-yemen-navigation-20260912",
    "desk": "japan",
    "deskSlugs": ["japan"],
    "section": "日本｜外交",
    "sectionLabel": "日本",
    "status": "LATEST",
    "title": "日本譴責胡塞武裝襲擊　強調曼德海峽安全關乎能源保障",
    "dek": "日本外務省9月12日發表聲明，譴責胡塞武裝近期針對也門及沙特的襲擊，並指保障曼德海峽自由安全航行對日本能源安全至關重要。",
    "summary": "日本外務省表示，胡塞武裝自7月宣布對沙特實施海上封鎖後持續發動軍事襲擊，造成包括平民在內的傷亡。東京再次要求胡塞武裝停止升級局勢，並表明會與國際社會合作推動也門及中東局勢降溫。",
    "body": "日本外務省9月12日由報道官北村俊博發表聲明，再次強烈譴責胡塞武裝近期針對也門及沙特阿拉伯的一連串襲擊。聲明指出，襲擊平民及民用設施，以及妨礙船舶自由、安全航行的行動均不能接受，並要求胡塞武裝避免在也門境內外進一步升級局勢。\n\n外務省同時把紅海安全與日本自身利益直接連結。聲明稱，也門穩定關乎整個中東局勢，而確保曼德海峽自由安全航行對包括日本在內的國際社會尤其重要，其中一個關鍵原因是能源安全。東京表示，會繼續與也門、沙特及其他國際伙伴合作，推動局勢盡快降溫。",
    "context": "曼德海峽連接紅海與亞丁灣，是亞洲與歐洲海運及能源供應的重要航道。近期胡塞武裝在紅海一帶擴大軍事行動，沙特能源基建亦受到襲擊，令日本等高度依賴進口能源的經濟體更加關注航運安全。",
    "why": "日本政府把曼德海峽安全明確列為能源安全議題，反映中東衝突已不只是外交事件，也直接牽動日本能源供應、運費及企業成本。",
    "watchNext": "留意日本會否進一步參與國際護航或外交協調，以及紅海航線、沙特能源設施和日本進口能源成本是否出現新的變化。",
    "sourceName": "日本外務省",
    "sourceUrl": "https://www.mofa.go.jp/press/statement/pageite_000001_01811.html",
    "sourcePublishedDate": "2026-09-12",
    "verifiedAt": "2026-09-12T20:20:00+08:00",
    "timeLabel": "9月12日20:20 HKT核實",
    "sources": [
        {"name": "日本外務省", "url": "https://www.mofa.go.jp/press/statement/pageite_000001_01811.html"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - VERIFIED
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
