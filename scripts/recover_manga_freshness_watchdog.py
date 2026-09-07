#!/usr/bin/env python3
"""Recover a stale Manga/Anime desk with a current, source-backed story.

This is invoked by the existing Live publication maintenance workflow. It does
not create a Live edition or schedule; it only refreshes the Manga/Anime rolling
desk when that desk has exceeded its existing freshness SLA.
"""
import datetime as dt
import json
from pathlib import Path

from desk_freshness_policy import PUBLIC_DESK_FRESHNESS_HOURS, editorial_story_time

ROOT = Path(__file__).resolve().parents[1]
DESK_PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))

STORY = {
    "id": "manga-anime-keroro-new-tv-anime-20260907",
    "desk": "manga-anime",
    "deskSlugs": ["manga-anime"],
    "section": "漫畫／動畫｜電視動畫",
    "status": "LATEST",
    "title": "《Keroro軍曹》相隔15年半推出全新電視動畫　10月3日開播並全面換上新聲優",
    "dek": "《Keroro軍曹☆》定於10月3日起在東京電視台系列播出，製作方同時公開首支正式預告、主視覺及新一代Keroro小隊聲優陣容。",
    "summary": "Bandai Namco Pictures公布《Keroro軍曹☆》將於10月3日起每逢星期六上午播出，這是系列自2011年3月以來相隔15年半再有全新電視動畫，主要角色聲優亦全面更新。",
    "body": "Bandai Namco Pictures於9月7日公布，《Keroro軍曹☆》將於10月3日起每逢星期六上午9時30分在東京電視台系列六局播出，並公開首支正式預告及主視覺。今次是《Keroro軍曹》自2011年3月以來，相隔15年半再推出全新電視動畫。\n\n官方亦公布Keroro小隊五名主要角色的新聲優陣容，並安排第1及第2集先行上映會。ORICON同日報道亦確認新作開播日期及主要聲優全面更替。",
    "context": "《Keroro軍曹》由吉崎觀音漫畫改編，2004年至2011年間曾播出長篇電視動畫，2026年6月亦推出新劇場版。",
    "why": "相隔15年半恢復全新電視動畫並全面更新主要聲優，是長壽動漫系列的重要製作及播映動向，適合歸入漫畫／動畫版。",
    "watchNext": "留意9月14日官方預告的下一輪新情報，以及正式播出前公布的追加角色、製作人員和先行上映詳情。",
    "sourceName": "Bandai Namco Pictures／ORICON NEWS",
    "sourceUrl": "https://www.oricon.co.jp/pressrelease/2978066/",
    "timeLabel": "9月7日16:16 HKT公布",
    "publishedAt": "2026-09-07T16:16:00+08:00",
    "verifiedAt": "2026-09-08T07:12:00+08:00",
    "sources": [
        {
            "name": "Bandai Namco Pictures",
            "url": "https://www.oricon.co.jp/pressrelease/2978066/"
        },
        {
            "name": "ORICON NEWS",
            "url": "https://www.oricon.co.jp/news/2478824/full/"
        }
    ]
}


def newest_age_hours(stories, now):
    stamps = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        stamp = editorial_story_time(story, now=now.astimezone(dt.timezone.utc))
        if stamp is not None:
            stamps.append(stamp.astimezone(HKT))
    if not stamps:
        return float("inf")
    return max(0.0, (now - max(stamps)).total_seconds() / 3600.0)


def main():
    data = json.loads(DESK_PATH.read_text(encoding="utf-8"))
    desks = data.setdefault("desks", {})
    current = desks.setdefault("manga-anime", [])
    now = dt.datetime.now(HKT)
    age = newest_age_hours(current, now)
    sla = PUBLIC_DESK_FRESHNESS_HOURS["manga-anime"]

    if age <= sla:
        print(f"MANGA_FRESHNESS_RECOVERY_SKIP age_h={age:.2f} sla_h={sla}")
        return

    story_id = STORY["id"]
    current[:] = [x for x in current if str(x.get("id") or "") != story_id]
    current.insert(0, STORY)
    DESK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MANGA_FRESHNESS_RECOVERY_ADD age_h={age:.2f} id={story_id}")


if __name__ == "__main__":
    main()
