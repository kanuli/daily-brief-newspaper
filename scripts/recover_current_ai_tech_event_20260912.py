#!/usr/bin/env python3
"""One-event fail-closed recovery for the current AI-Tech desk.

Uses a genuinely current Reuters report and its real publication time.
It never retimestamps stale content: after the 12-hour AI-Tech SLA the script
becomes a no-op and lets freshness validation fail closed.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
PUBLISHED = dt.datetime.fromisoformat("2026-09-12T03:15:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "ai-tech-us-senate-duty-of-care-frontier-models-20260912",
    "desk": "ai-tech",
    "deskSlugs": ["ai-tech"],
    "section": "AI／科技｜監管與安全",
    "sectionLabel": "AI／科技",
    "status": "LATEST",
    "title": "美參院研AI「注意義務」法案　擬要求前沿模型防範重大災難風險",
    "dek": "跨黨派參議員正商討要求先進AI開發商承擔安全設計責任，政府亦可能獲權阻止被判定為不安全的模型發布。",
    "summary": "路透社報道，美國參議院跨黨派談判正研究一項針對最先進AI模型的監管框架，擬要求開發商承擔「注意義務」，在產品設計階段防範核、生物武器等重大災難風險；方案亦討論由聯邦政府阻止被判定為不安全的模型發布，企業可向聯邦法院提出挑戰。",
    "body": "美國國會正重新討論如何監管最先進的人工智能系統。路透社引述參議院助理及參與談判人士報道，跨黨派議員研究建立AI開發商的「注意義務」，要求企業在設計及發布模型時，以避免重大災難風險為明確責任，包括防止系統被用於設計核武或生物武器。\n\n方案亦考慮賦予聯邦政府權力，在特定模型被判定不安全時阻止其發布，同時讓企業可在聯邦法院挑戰政府決定。談判仍未定案，並可能涉及部分州級AI規例的聯邦優先權。由於國會在11月中期選舉前會期有限，法案能否及時完成仍存在很大不確定性。",
    "context": "近期多宗先進AI系統偏離人類指令、進行未授權網絡行動的事件，加上前業界研究員公開警告前沿模型風險，令華府再次加快討論全國性AI安全規則。",
    "why": "若「注意義務」及政府阻止發布權最終成法，將直接影響OpenAI、Google、Anthropic等前沿模型開發商的測試、發布節奏、合規成本及州級監管格局。",
    "watchNext": "留意參議院談判能否形成正式文本、是否要求國家實驗室參與模型測試，以及聯邦規則會否凌駕州級AI安全法。",
    "sourceName": "Reuters",
    "sourceUrl": "https://www.reuters.com/legal/litigation/us-senate-negotiators-consider-requiring-ai-firms-mitigate-known-major-risks-2026-09-11/",
    "publishedAt": "2026-09-12T03:15:00+08:00",
    "timeLabel": "9月12日03:15 HKT",
    "sources": [
        {"name": "Reuters", "url": "https://www.reuters.com/legal/litigation/us-senate-negotiators-consider-requiring-ai-firms-mitigate-known-major-risks-2026-09-11/"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - PUBLISHED
    if age < dt.timedelta(0) or age > MAX_AGE:
        print(f"AI_TECH_CURRENT_RECOVERY_NOOP age_h={age.total_seconds()/3600:.2f}")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    desks = data.get("desks")
    if not isinstance(desks, dict):
        raise SystemExit("desk-latest desks missing/invalid")
    if not isinstance(desks.get("ai-tech"), list):
        raise SystemExit("ai-tech desk missing/invalid")

    stories = desks["ai-tech"]
    if any(isinstance(s, dict) and s.get("id") == STORY["id"] for s in stories):
        print("AI_TECH_CURRENT_RECOVERY_NOOP already-present")
        return 0

    stories.insert(0, dict(STORY))
    PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"AI_TECH_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
