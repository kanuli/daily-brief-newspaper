#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Hong Kong desk.

Uses a genuinely current Reuters report and its real publication time.
It never retimestamps stale content: after the 12-hour Hong Kong SLA the script
becomes a no-op and lets freshness validation fail closed.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T18:47:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "hong-kong-zai-share-placement-convertible-bonds-20260911",
    "desk": "hong-kong",
    "deskSlugs": ["hong-kong"],
    "section": "香港｜資本市場",
    "sectionLabel": "香港",
    "status": "LATEST",
    "title": "智譜AI在港啟動約50億美元再融資　配股兼發可換股債",
    "dek": "北京AI企業智譜AI在香港啟動約20億美元配股及約30億美元可換股債發售，資金擬投向研發、算力基建及擴張。",
    "summary": "Reuters引述交易條款報道，智譜AI在香港啟動約20億美元新股配售，並同步出售約30億美元可換股債。配股價為每股714港元，較周五收市價折讓約一成；公司表示集資將用於研發、算力基建、擴張及潛在投資。",
    "body": "北京人工智能企業智譜AI在香港啟動新一輪大型融資。Reuters引述交易條款報道，公司計劃配售2,197萬股香港新股，每股作價714港元，較周五收市價793港元折讓約10%，集資規模約20億美元。\n\n公司同時推出約30億美元可換股債，兩項交易彼此獨立。智譜AI今年1月在港上市，7月再透過後續股份發售集資約40億美元。今次所得資金擬用於研發、算力基建、業務擴張、策略投資及收購等用途，反映AI企業持續透過香港資本市場籌集高額算力及人才投入所需資金。",
    "context": "香港今年新股及再融資活動活躍，多家中國AI企業亦正尋求在港上市或擴大融資。大型配股及可換股債交易同時考驗市場承接力與估值。",
    "why": "智譜AI一次過啟動約50億美元股份與債券融資，顯示香港仍是中國AI企業重要的國際集資平台，亦會影響本地股票市場的資金供求與科技股估值。",
    "watchNext": "留意最終定價、認購需求、可換股債條款，以及交易完成後智譜AI股價和香港AI概念股的資金流向。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/world/asia-pacific/china-ai-developer-zai-launches-5-billion-hong-kong-share-convertible-bond-sales-2026-09-11/",
    "publishedAt": "2026-09-11T18:47:00+08:00",
    "timeLabel": "9月11日18:47 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/world/asia-pacific/china-ai-developer-zai-launches-5-billion-hong-kong-share-convertible-bond-sales-2026-09-11/"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - PUBLISHED
    if age < dt.timedelta(0) or age > MAX_AGE:
        print(f"HONG_KONG_CURRENT_RECOVERY_NOOP age_h={age.total_seconds()/3600:.2f}")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    desks = data.get("desks")
    if not isinstance(desks, dict):
        raise SystemExit("desk-latest desks missing/invalid")
    if not isinstance(desks.get("hong-kong"), list):
        raise SystemExit("hong-kong desk missing/invalid")

    stories = desks["hong-kong"]
    if any(isinstance(s, dict) and s.get("id") == STORY["id"] for s in stories):
        print("HONG_KONG_CURRENT_RECOVERY_NOOP already-present")
        return 0

    stories.insert(0, dict(STORY))
    PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"HONG_KONG_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
