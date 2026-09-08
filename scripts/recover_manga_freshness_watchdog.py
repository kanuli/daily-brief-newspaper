#!/usr/bin/env python3
"""Recover a stale Manga/Anime desk with a current, source-backed story.

This is invoked by the existing Live publication maintenance workflow. It does
not create a Live edition or schedule; it only refreshes the Manga/Anime rolling
desk when that desk has exceeded its existing freshness SLA. The recovery story
must itself still satisfy the desk SLA.
"""
import datetime as dt
import json
from pathlib import Path

from desk_freshness_policy import PUBLIC_DESK_FRESHNESS_HOURS, editorial_story_time

ROOT = Path(__file__).resolve().parents[1]
DESK_PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))

STORY = {
    "id": "manga-anime-marriage-toxin-season2-visual-20260908",
    "desk": "manga-anime",
    "deskSlugs": ["manga-anime"],
    "section": "漫畫／動畫｜電視動畫",
    "status": "LATEST",
    "title": "《Marriage Toxin》動畫第2季公開主視覺　2027年1月接續播出",
    "dek": "改編自《少年Jump+》同名漫畫的《Marriage Toxin》公開第2季主視覺及宣傳影片，續篇定於2027年1月在關西電視台／富士電視台動畫時段播出。",
    "summary": "MANTANWEB 9月8日報道，《Marriage Toxin》電視動畫第2季公開主視覺及宣傳影片；畫面延續殺手下呂光與婚姻詐欺師城崎梅的搭檔主線，並確認2027年1月開播。",
    "body": "MANTANWEB於9月8日上午10時報道，集英社《少年Jump+》連載漫畫《Marriage Toxin》改編電視動畫已公開第2季主視覺及宣傳影片。主視覺描繪使用毒術的下呂光手持注射器、城崎梅手持花束，背景取自第一季的重要場景。\n\n第1季已於2026年4月至6月在關西電視台／富士電視台動畫時段播出；第2季確認於2027年1月在同一時段接續推出。動畫由Bones Film製作，主要聲優陣容亦隨新一輪宣傳資料列出。",
    "context": "《Marriage Toxin》原作由靜脈負責故事、依田瑞稀作畫，2022年起於《少年Jump+》連載，結合戰鬥、殺手世界觀與戀愛喜劇元素。",
    "why": "第2季主視覺、宣傳影片及2027年1月播映安排屬當日實質動畫製作進展，應只歸入漫畫／動畫版。",
    "watchNext": "留意第2季確實首播日期、追加聲優、主題曲及後續正式預告。",
    "sourceName": "MANTANWEB",
    "sourceUrl": "https://en.mantan-web.jp/e_article/20260907dog00m200073000a.html",
    "timeLabel": "9月8日10:00 HKT報道",
    "publishedAt": "2026-09-08T10:00:00+08:00",
    "verifiedAt": "2026-09-08T18:18:00+08:00",
    "sources": [
        {
            "name": "MANTANWEB",
            "url": "https://en.mantan-web.jp/e_article/20260907dog00m200073000a.html"
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

    story_age = newest_age_hours([STORY], now)
    if story_age > sla:
        raise SystemExit(
            f"MANGA_FRESHNESS_RECOVERY_STORY_STALE age_h={story_age:.2f} sla_h={sla}; refusing false repair"
        )

    story_id = STORY["id"]
    current[:] = [x for x in current if str(x.get("id") or "") != story_id]
    current.insert(0, STORY)
    DESK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MANGA_FRESHNESS_RECOVERY_ADD age_h={age:.2f} id={story_id}")


if __name__ == "__main__":
    main()
