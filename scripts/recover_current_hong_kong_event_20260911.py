#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Hong Kong desk.

Uses a genuinely current source report and its real publication time.
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
PUBLISHED = dt.datetime.fromisoformat("2026-09-12T12:46:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "hong-kong-police-public-event-risk-assessment-20260912",
    "desk": "hong-kong",
    "deskSlugs": ["hong-kong"],
    "section": "香港｜公共安全",
    "sectionLabel": "香港",
    "status": "LATEST",
    "title": "警務處：公眾活動申請續按公共安全、秩序及國安因素評估",
    "dek": "警務處處長周一鳴在警察學院結業會操後表示，警方處理公眾活動申請時會按整體情況評估公共安全、公共秩序及國家安全等因素。",
    "summary": "無綫新聞9月12日報道，警務處處長周一鳴在香港警察學院結業會操後表示，警方一向按照《公安條例》處理公眾活動通知，並會綜合考慮公共安全、公共秩序及國家安全等因素。他又指現時社會整體氣氛平和，但警方仍會留意潛在風險。",
    "body": "香港警察學院9月12日舉行結業會操。警務處處長周一鳴在會操後會見傳媒時表示，警方處理公眾集會及相關活動通知時，一向會按《公安條例》及整體情況作風險評估，考慮因素包括公共安全、公共秩序以及國家安全。\n\n周一鳴表示，現時香港整體社會氣氛平和，但警方認為仍需對潛在國安及公共秩序風險保持警覺。當日多間本地傳媒亦報道同一場結業會操及警方高層的公開發言。",
    "context": "警方依法處理公眾活動通知及風險評估，相關判斷會因活動性質、公共安全及秩序等實際情況而異。",
    "why": "警務處處長就公眾活動審批及風險評估準則作出當日公開說明，直接關乎本地公共安全及市民舉辦公共活動時的執法安排。",
    "watchNext": "留意警方日後處理具體公眾活動通知時公布的條件或安排，以及是否有新的公共秩序或國安執法指引。",
    "sourceName": "無綫新聞 / Now新聞台",
    "sourceUrl": "https://news.tvb.com/tc/1194806-Policecommissionerwarnsagainstthosewhostirchaos",
    "publishedAt": "2026-09-12T12:46:00+08:00",
    "timeLabel": "9月12日12:46 HKT",
    "sources": [
        {"name": "無綫新聞", "url": "https://news.tvb.com/tc/1194806-Policecommissionerwarnsagainstthosewhostirchaos"},
        {"name": "Now新聞台", "url": "https://hk.news.yahoo.com/%E5%91%A8-%E9%B3%B4-%E6%9C%AC%E6%B8%AF%E6%95%B4%E9%AB%94%E7%A4%BE%E6%9C%83%E6%B0%A3%E6%B0%9B%E5%B9%B3%E5%92%8C-%E4%BD%86%E4%BB%8D%E6%9A%97%E6%B9%A7%E8%99%95%E8%99%95-%E6%B1%9F%E7%93%94%E5%BA%AD%E5%A0%B1%E9%81%93-051735738.html"}
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
