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
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T10:30:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "japan-katayama-us-fx-coordination-20260911",
    "desk": "japan",
    "deskSlugs": ["japan"],
    "section": "日本｜政策",
    "sectionLabel": "日本",
    "status": "LATEST",
    "title": "片山皋月：日美將續就匯市密切溝通　維持有序外匯市場",
    "dek": "日本財相片山皋月表示，日美聯手干預日圓並發表聯合聲明後，政策立場沒有改變，政府會繼續與美國財政部保持密切溝通。",
    "summary": "日本財相片山皋月周五表示，日本政府會繼續與美國密切溝通，以確保外匯市場有序運作。她強調，日美早前協調干預日圓並發表聯合聲明後，日本的政策立場沒有改變。",
    "body": "日本財相片山皋月周五在例行記者會表示，日本會繼續與美國財政部保持密切溝通，確保外匯市場有序運作。她說，自日美早前採取協調干預並發表聯合聲明以來，政府的政策立場完全沒有改變。\n\n被問到美國財長貝森特近日警告市場不要押注日圓下跌，片山表示，有關說法是相當直接的市場觀點。日圓走勢、進口成本及日本央行下一步政策仍受市場密切注視，日美官方協調亦繼續成為匯市的重要政策訊號。",
    "context": "日美早前曾採取協調行動支持日圓；市場目前同時評估日本通脹、油價及日本央行政策前景。",
    "why": "日本政府確認與美國在匯市政策上的協調立場沒有改變，直接關乎日圓穩定、輸入通脹及日本宏觀政策環境。",
    "watchNext": "留意日本財務省與美國財政部後續表態、日圓波動，以及日本央行下周政策會議對利率與通脹風險的最新判斷。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/world/asia-pacific/japan-maintain-close-communication-with-us-currency-markets-katayama-says-2026-09-11/",
    "publishedAt": "2026-09-11T10:30:00+08:00",
    "timeLabel": "9月11日10:30 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/world/asia-pacific/japan-maintain-close-communication-with-us-currency-markets-katayama-says-2026-09-11/"}
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
