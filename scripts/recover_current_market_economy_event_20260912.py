#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Market-Economy desk.

Uses a genuinely current Reuters market-regulation report and its real
publication time. It never retimestamps stale content: after the 8-hour
Market-Economy SLA the script becomes a no-op and lets validation fail closed.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
PUBLISHED = dt.datetime.fromisoformat("2026-09-12T14:56:08+08:00")
MAX_AGE = dt.timedelta(hours=8)

STORY = {
    "id": "market-economy-india-sebi-derivatives-expiry-pricing-20260912",
    "desk": "market-economy",
    "deskSlugs": ["market-economy"],
    "section": "財經｜金融市場監管",
    "sectionLabel": "財經",
    "status": "LATEST",
    "title": "印度擬重整衍生工具到期日結算價　SEBI檢討收市競價機制",
    "dek": "印度證券交易委員會提出兩套到期日結算價方案，回應新收市競價機制推出後衍生工具到期日出現明顯市場波動。",
    "summary": "路透社報道，印度SEBI周六提出檢討指數及個股衍生工具到期日的結算價計算方法，包括把正常交易最後30分鐘與10分鐘收市競價合併計算，或暫時只採用正常交易最後30分鐘價格。",
    "body": "印度證券交易委員會SEBI周六發表諮詢文件，提出檢討指數及個股衍生工具在到期日的結算價計算方法。路透社報道，SEBI列出兩個主要選項：其一是把正常交易最後30分鐘與其後10分鐘收市競價時段的成交一併計算；其二則是在至少一年內暫時把衍生工具結算與收市競價分開，只使用正常交易最後30分鐘的價格。\n\nSEBI同時建議收緊收市競價期間的落盤及撤單安排，包括限制撤銷偏離參考價超過1%的限價盤，以及縮短部分衍生工具收市後交易時段。監管機構表示，目標不是取消收市競價，而是因應到期日出現的急劇波動改善價格發現與結算機制；公眾諮詢期至10月3日。",
    "context": "印度在8月3日於有衍生工具交易的股票現貨市場引入Closing Auction Session，原意是提高收市價格發現的透明度及效率，但到期日價格波動令監管機構迅速啟動檢討。",
    "why": "結算價規則直接影響指數及個股期貨、期權的到期損益與套利行為；若制度修改，可改變印度大型股票及衍生工具在收市前後的流動性、波動及交易策略。",
    "watchNext": "留意SEBI在10月3日諮詢截止後採用哪一套結算方案、交易所的實施時間表，以及新規能否降低到期日收市前後的異常波動。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/world/india/india-regulator-plans-changes-set-expiry-days-settlement-prices-derivatives-2026-09-12/",
    "publishedAt": "2026-09-12T14:56:08+08:00",
    "timeLabel": "9月12日14:56 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/world/india/india-regulator-plans-changes-set-expiry-days-settlement-prices-derivatives-2026-09-12/"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - PUBLISHED
    if age < dt.timedelta(0) or age > MAX_AGE:
        print(f"MARKET_ECONOMY_CURRENT_RECOVERY_NOOP age_h={age.total_seconds()/3600:.2f}")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    desks = data.get("desks")
    if not isinstance(desks, dict):
        raise SystemExit("desk-latest desks missing/invalid")
    if not isinstance(desks.get("market-economy"), list):
        raise SystemExit("market-economy desk missing/invalid")

    stories = desks["market-economy"]
    if any(isinstance(s, dict) and s.get("id") == STORY["id"] for s in stories):
        print("MARKET_ECONOMY_CURRENT_RECOVERY_NOOP already-present")
        return 0

    stories.insert(0, dict(STORY))
    PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"MARKET_ECONOMY_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
