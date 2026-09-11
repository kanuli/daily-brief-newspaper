#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Manga/Anime desk.

The event is source-backed and carries its real publication timestamp. It is
eligible only for 24 hours; after that this script becomes a no-op rather than
retimestamping old news.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
PUBLISHED = dt.datetime.fromisoformat("2026-09-10T17:38:00+08:00")
MAX_AGE = dt.timedelta(hours=24)

STORY = {
    "id": "manga-anime-apothecary-diaries-console-game-20260910",
    "desk": "manga-anime",
    "deskSlugs": ["manga-anime"],
    "section": "漫畫・動畫｜《藥師少女的獨語》",
    "sectionLabel": "漫畫 / Anime",
    "status": "LATEST",
    "title": "《藥師少女的獨語》首度改編家用主機遊戲　日向夏原案新故事2027年初推出",
    "dek": "Koei Tecmo、Gust與TOHO Games公布《The Apothecary Diaries: The False Imperial Brother》，將登陸Switch 2、Switch、PS5及PC。",
    "summary": "《藥師少女的獨語》首次推出家用主機遊戲，原作者日向夏負責新故事原案；玩家將操作貓貓調查後宮、市井與花街的「五個謎」與「五個詛咒」。",
    "body": "Koei Tecmo與開發商Gust聯同TOHO Games公布《The Apothecary Diaries: The False Imperial Brother》，是《藥師少女的獨語》首次改編家用主機遊戲，預定2027年初登陸Nintendo Switch 2、Switch、PlayStation 5及Steam。原作者日向夏為遊戲構思全新故事與角色。\n\n遊戲延續貓貓以藥學知識和推理破解事件的核心設定，玩家需要蒐集證言及證據、調配藥物，再處理圍繞後宮、花街與京城的連串異象。由原作者參與新故事，加上跨四個平台推出，令這次企劃不只是授權商品，而是作品IP向互動娛樂擴張的重要一步。",
    "context": "《藥師少女的獨語》已由輕小說、漫畫與電視動畫建立大型受眾；今次是系列首次把完整原創故事帶到家用主機及PC遊戲。",
    "why": "原作者參與、TOHO Games與Gust合作及多平台同步布局，反映熱門漫畫動畫IP持續向遊戲市場延伸。",
    "watchNext": "留意確實發售日期、價格、更多玩法展示，以及日本以外語言與發行安排。",
    "sourceName": "Koei Tecmo / ABEMA",
    "sourceUrl": "https://www.koeitecmoamerica.com/news/investigate-palace-conspiracies-in-koei-tecmos-the-apothecary-diaries-the-false-imperial-brother/",
    "publishedAt": "2026-09-10T17:38:00+08:00",
    "timeLabel": "9月10日17:38 HKT",
    "sources": [
        {"name": "Koei Tecmo", "url": "https://www.koeitecmoamerica.com/news/investigate-palace-conspiracies-in-koei-tecmos-the-apothecary-diaries-the-false-imperial-brother/"},
        {"name": "ABEMA TIMES", "url": "https://times.abema.tv/articles/-/10272308"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - PUBLISHED
    if age < dt.timedelta(0) or age > MAX_AGE:
        print(f"MANGA_CURRENT_RECOVERY_NOOP age_h={age.total_seconds()/3600:.2f}")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    desks = data.get("desks")
    if not isinstance(desks, dict) or not isinstance(desks.get("manga-anime"), list):
        raise SystemExit("manga-anime desk missing/invalid")

    stories = desks["manga-anime"]
    if any(isinstance(s, dict) and s.get("id") == STORY["id"] for s in stories):
        print("MANGA_CURRENT_RECOVERY_NOOP already-present")
        return 0

    stories.insert(0, STORY)
    PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"MANGA_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
