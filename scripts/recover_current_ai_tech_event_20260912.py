#!/usr/bin/env python3
"""One-event fail-closed recovery for the current AI-Tech desk.

Uses a genuinely current September 12 AI Tinkerers event backed by official
chapter/global event pages. Because the event pages provide the event date and
local schedules rather than a news publication timestamp, freshness is based
on the actual editorial verification time; no source publication time is
invented.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
VERIFIED = dt.datetime.fromisoformat("2026-09-12T20:24:00+08:00")
MAX_AGE = dt.timedelta(hours=12)

STORY = {
    "id": "ai-tech-agents-everywhere-global-hackathon-20260912",
    "desk": "ai-tech",
    "deskSlugs": ["ai-tech"],
    "section": "AI／科技｜代理程式",
    "sectionLabel": "AI／科技",
    "status": "LATEST",
    "title": "AI Tinkerers全球同日辦代理程式Hackathon　OpenAI等支持跨平台實作",
    "dek": "AI Tinkerers於9月12日在多個城市舉行「Agents, Everywhere」全球Hackathon，要求參加者把AI代理程式帶入電郵、瀏覽器、流動裝置、語音及工作平台等真實場景。",
    "summary": "AI Tinkerers多個城市分會9月12日同步舉行「Agents, Everywhere」全球Hackathon，OpenAI為主要支持伙伴，CopilotKit、OpenRouter等亦參與。參賽團隊要製作可在現有工作與通訊環境中運作的AI代理程式，並向同一全球提交池遞交公開程式碼及示範。",
    "body": "AI Tinkerers於9月12日在多個城市同步舉行「Agents, Everywhere」全球Hackathon，活動由OpenAI等伙伴支持。官方活動資料顯示，今次題目不鼓勵把代理程式留在獨立聊天視窗，而是要求開發者把可執行任務的AI代理程式放入人們原本已使用的環境，包括Slack、Teams、電郵、文件、瀏覽器、流動裝置、語音、穿戴裝置及機械人。\n\n各地團隊參與同一全球提交池，合資格作品需要提供公開GitHub程式庫、書面說明及短片示範。活動重點由單純模型能力轉向代理程式如何在真實工具和工作流程中安全、可靠地執行任務，反映業界競爭焦點正由聊天介面進一步移向可跨應用操作的agentic AI。",
    "context": "大型AI公司近月持續推出可使用工具及跨應用執行工作的代理式功能，同時自主代理程式的權限、可靠性和安全邊界亦成為產業核心議題。",
    "why": "全球同步實作活動把agentic AI由產品宣傳帶到實際開發場景，可觀察開發者最重視的使用介面、工具整合及安全模式，亦反映AI產品正加速由回答問題轉向直接執行工作。",
    "watchNext": "留意全球提交作品集中在哪些應用場景、OpenAI及其他贊助商會否把相關開發模式吸收到正式產品，以及跨平台代理程式的權限和安全設計會否出現新的共同做法。",
    "sourceName": "AI Tinkerers",
    "sourceUrl": "https://aitinkerers.org/events",
    "sourcePublishedDate": "2026-09-12",
    "verifiedAt": "2026-09-12T20:24:00+08:00",
    "timeLabel": "9月12日20:24 HKT核實",
    "sources": [
        {"name": "AI Tinkerers", "url": "https://aitinkerers.org/events"},
        {"name": "AI Tinkerers Portland", "url": "https://portland.aitinkerers.org/p/agents-everywhere-beyond-the-chatbot-global-hackathon"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - VERIFIED
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
