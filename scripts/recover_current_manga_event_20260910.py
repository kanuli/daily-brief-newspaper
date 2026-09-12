#!/usr/bin/env python3
"""One-event fail-closed recovery for the current Manga/Anime desk.

Uses a current first-party U-NEXT announcement and a real verification time.
The source page itself is dated 2026-09-12. No publication clock time is
invented: verifiedAt records when the current official announcement was checked.
The recovery remains eligible for only 24 hours, then becomes a no-op.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
VERIFIED = dt.datetime.fromisoformat("2026-09-12T17:17:00+08:00")
MAX_AGE = dt.timedelta(hours=24)

STORY = {
    "id": "manga-anime-tiger-bunny-stage-unext-20260912",
    "desk": "manga-anime",
    "deskSlugs": ["manga-anime"],
    "section": "漫畫・動畫｜《TIGER & BUNNY》",
    "sectionLabel": "漫畫 / Anime",
    "status": "LATEST",
    "title": "《TIGER & BUNNY》15周年舞台化　U-NEXT獨家直播10月4日兩場",
    "dek": "U-NEXT於9月12日公布，動畫《TIGER & BUNNY》15周年舞台作品將於9月19日起公演，10月4日午、晚兩場由平台獨家直播。",
    "summary": "U-NEXT官方公布《TIGER & BUNNY》THE STAGE直播安排。舞台由spi飾演鏑木・T・虎徹、塩田一期飾演巴納比・布魯克斯Jr.，10月4日13時及18時兩場大千秋樂將提供獨家直播及其後回看。",
    "body": "U-NEXT於9月12日公布，為紀念動畫《TIGER & BUNNY》播出15周年而製作的《TIGER & BUNNY》THE STAGE，將於9月19日起正式公演。平台確認10月4日13時及18時兩場大千秋樂會作獨家直播，兩場均安排演員直播後特別內容，並提供限定回看。\n\n舞台版由spi飾演鏑木・T・虎徹／Wild Tiger，塩田一期飾演Barnaby Brooks Jr.，並集合多名角色演員。官方同時推出單場及兩場套票，後者附特典照片；相關直播票務及活動安排已在U-NEXT公布。",
    "context": "《TIGER & BUNNY》自2011年首播，2022年推出《TIGER & BUNNY 2》。2026年是動畫15周年，舞台化屬系列周年企劃的重要延伸。",
    "why": "這是動畫IP在15周年期間落實的新舞台及串流安排，直接涉及作品官方延伸企劃、演員陣容及觀眾可觀看渠道，屬當日可核實的Manga/Anime版面資訊。",
    "watchNext": "留意9月19日開演後評價、10月4日直播實際安排，以及15周年是否再公布動畫、影像作品或其他官方企劃。",
    "sourceName": "U-NEXT",
    "sourceUrl": "https://www.unext.co.jp/ja/press-room/tiger-bunny-thestage-2026-09-12",
    "verifiedAt": "2026-09-12T17:17:00+08:00",
    "timeLabel": "9月12日17:17 HKT核實",
    "sources": [
        {"name": "U-NEXT 官方新聞稿", "url": "https://www.unext.co.jp/ja/press-room/tiger-bunny-thestage-2026-09-12"}
    ]
}


def main() -> int:
    now = dt.datetime.now(HKT)
    age = now - VERIFIED
    if age < dt.timedelta(0) or age > MAX_AGE:
        print(f"MANGA_CURRENT_RECOVERY_NOOP age_h={age.total_seconds()/3600:.2f}")
        return 0

    data = json.loads(PATH.read_text(encoding="utf-8"))
    desks = data.get("desks")
    if not isinstance(desks, dict) or not isinstance(desks.get("manga-anime"), list):
        raise SystemExit("manga-anime desk missing/invalid")

    stories = desks["manga-anime"]
    for idx, story in enumerate(stories):
        if isinstance(story, dict) and story.get("id") == STORY["id"]:
            if story == STORY:
                print("MANGA_CURRENT_RECOVERY_NOOP already-current")
                return 0
            stories[idx] = dict(STORY)
            PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"MANGA_CURRENT_RECOVERY_CORRECTED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
            return 0

    stories.insert(0, dict(STORY))
    PATH.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"MANGA_CURRENT_RECOVERY_ADDED id={STORY['id']} age_h={age.total_seconds()/3600:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
