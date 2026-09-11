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
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T18:49:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "japan-yen-seven-month-high-boj-tightening-20260911",
    "desk": "japan",
    "deskSlugs": ["japan"],
    "section": "日本｜經濟",
    "sectionLabel": "日本",
    "status": "LATEST",
    "title": "日圓升至七個月高位　市場聚焦日本央行加快收緊政策",
    "dek": "Reuters周五市場回顧指出，日圓本周顯著走強，投資者加大押注日本央行收緊政策，並重新評估日本資金回流海外資產的可能性。",
    "summary": "Reuters在周五金融市場回顧中指出，日圓升至約七個月高位，市場對日本央行加快收緊政策的預期升溫。日本利率正常化及潛在資金回流，正成為全球債券與外匯市場的重要變數。",
    "body": "日圓本周顯著走強，成為全球市場焦點之一。Reuters周五的金融市場回顧指出，投資者正提高對日本央行更快收緊貨幣政策的預期，日圓升至約七個月高位；市場同時關注日本投資者會否因本土收益率上升而把部分海外資金調回國內。\n\n日本貨幣政策正常化的影響不只限於匯市。日本長期是全球低成本資金的重要來源，若利率繼續上升並推動資金回流，可能改變國際債券與股票市場的資金配置。市場下一個焦點是日本央行下周政策會議，以及央行對加息步伐和通脹風險的最新判斷。",
    "context": "日本央行正處於多年超寬鬆政策後的正常化階段，而日圓走勢、能源成本與國內通脹仍會影響加息節奏。",
    "why": "日圓與日本利率不只影響本地家庭和企業成本，也牽動全球套息交易及日本資金的海外配置，因此政策預期變化具有跨市場影響。",
    "watchNext": "留意日本央行下周議息結果、總裁植田和男對未來加息速度的說法，以及日圓和日本國債收益率是否延續升勢。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/commentary/reuters-open-interest/triple-digit-oil-yen-whiplash-2000-iphone-financial-week-five-charts-2026-09-11/",
    "publishedAt": "2026-09-11T18:49:00+08:00",
    "timeLabel": "9月11日18:49 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/commentary/reuters-open-interest/triple-digit-oil-yen-whiplash-2000-iphone-financial-week-five-charts-2026-09-11/"}
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
