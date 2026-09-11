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
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T22:29:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "hong-kong-pillar-of-shame-denmark-return-talks-20260911",
    "desk": "hong-kong",
    "deskSlugs": ["hong-kong"],
    "section": "香港｜司法與社會",
    "sectionLabel": "香港",
    "status": "LATEST",
    "title": "國殤之柱作者擬促丹麥政府與港府交涉　要求取回被扣雕塑",
    "dek": "丹麥雕塑家高志活表示，將尋求丹麥當局把作品列作文化遺產並與香港方面交涉；港府則反駁其所有權說法。",
    "summary": "《南華早報》報道，國殤之柱作者、丹麥雕塑家高志活表示，計劃要求丹麥政府正式把雕塑列為藝術品及丹麥文化遺產，並與香港方面交涉取回作品。香港官員則表示，相關雕塑過往曾交予已解散的香港市民支援愛國民主運動聯合會，對其所有權主張提出異議。",
    "body": "八米高的「國殤之柱」處置問題再次受到關注。丹麥雕塑家高志活向《南華早報》表示，他準備要求丹麥政府正式確認作品屬藝術品及丹麥文化遺產，並由官方與香港方面交涉，希望把雕塑交還其所稱的合法持有人。\n\n高志活稱已向丹麥國會外交政策委員會提出事件，歐洲議會跨黨派議員及歐盟駐港辦事處亦有跟進。香港方面則反駁其所有權說法，指出作品過往與已解散的支聯會存在安排。事件在香港法院就支聯會前領導人國安案件判刑後再度升溫，作品未來如何處理仍有待司法及行政程序釐清。",
    "context": "國殤之柱自1997年起曾長期在香港大學展示，2021年被校方移走，之後在相關國安案件中成為證物。作者多年來一直要求取回作品。",
    "why": "事件牽涉藝術品所有權、司法證物處置及香港與丹麥之間可能出現的外交交涉，亦可能成為近期國安案件後續的一項具體爭議。",
    "watchNext": "留意丹麥政府是否正式介入、香港法院或相關部門如何處理雕塑，以及作品所有權和證物處置是否出現新的法律程序。",
    "sourceName": "South China Morning Post",
    "sourceUrl": "https://www.scmp.com/news/hong-kong/law-and-crime/article/3367259/pillar-shame-sculptor-ask-denmark-negotiate-artworks-return",
    "publishedAt": "2026-09-11T22:29:00+08:00",
    "timeLabel": "9月11日22:29 HKT",
    "sources": [
        {"name": "South China Morning Post", "url": "https://www.scmp.com/news/hong-kong/law-and-crime/article/3367259/pillar-shame-sculptor-ask-denmark-negotiate-artworks-return"}
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
