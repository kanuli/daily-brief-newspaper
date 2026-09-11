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
PUBLISHED = dt.datetime.fromisoformat("2026-09-11T18:10:00+08:00")
MAX_AGE = dt.timedelta(hours=24)

STORY = {
    "id": "manga-anime-sound-euphonium-final-chapter-part2-20260911",
    "desk": "manga-anime",
    "deskSlugs": ["manga-anime"],
    "section": "漫畫・動畫｜《吹響吧！上低音號》",
    "sectionLabel": "漫畫 / Anime",
    "status": "LATEST",
    "title": "《吹響吧！上低音號》迎來動畫完結　《最終樂章》後篇日本上映",
    "dek": "由電視動畫第三季重新構成並加入大量新畫面的《最終樂章 吹響吧！上低音號》後篇9月11日在日本上映，為這套自2015年起延續約11年的動畫系列收結。",
    "summary": "《吹響吧！上低音號》動畫系列迎來最終章後篇。作品以北宇治高中吹奏樂部為舞台，劇場版在第三季素材基礎上重新剪輯並新增多段場面；製作團隊亦公開小川太一導演為上映繪製的紀念插畫。",
    "body": "MANTANWEB報道，《最終樂章 吹響吧！上低音號》後篇於9月11日在日本上映。劇場版把《吹響吧！上低音號3》的內容重新構成，除重新處理既有畫面外，亦加入文化祭演奏、畢業禮等電視版未有呈現的新片段，為黃前久美子等北宇治高中吹奏樂部成員的故事收結。\n\n系列電視動畫第一季於2015年4月首播，其後推出第二、第三季及多部劇場作品。《最終樂章》前篇已於今年4月24日上映，後篇則標誌這套由京都動畫製作、延續約11年的動畫系列正式走到終點。上映同日，製作團隊亦公開由導演小川太一繪製、久美子與麗奈背靠背牽手的紀念插畫。",
    "context": "《吹響吧！上低音號》改編自武田綾乃小說，以京都府宇治市為重要舞台。動畫系列長期由京都動畫製作，第三季於2024年播出。",
    "why": "後篇上映為延續約11年的主要動畫敘事畫上句號，亦是京都動畫代表系列的一個重要節點，對長期觀眾與作品IP後續發展均具指標意義。",
    "watchNext": "留意日本上映後的票房與觀眾反應、海外上映與串流安排，以及官方會否公布系列後續活動或紀念企劃。",
    "sourceName": "MANTANWEB / Kyoto Animation",
    "sourceUrl": "https://mantan-web.jp/article/20260911dog00m200047000a.html",
    "publishedAt": "2026-09-11T18:10:00+08:00",
    "timeLabel": "9月11日18:10 HKT",
    "sources": [
        {"name": "MANTANWEB", "url": "https://mantan-web.jp/article/20260911dog00m200047000a.html"},
        {"name": "Kyoto Animation", "url": "https://anime-eupho.com/"}
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
