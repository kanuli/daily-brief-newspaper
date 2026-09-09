#!/usr/bin/env python3
"""Recover stale specialist desks with current, source-backed stories.

This existing Live-maintenance helper does not create a Live edition or a new
schedule. It refreshes only desks that have exceeded their existing freshness
SLA, and refuses to use a recovery story that is itself stale.
"""
import datetime as dt
import json
from pathlib import Path

from desk_freshness_policy import PUBLIC_DESK_FRESHNESS_HOURS, editorial_story_time

ROOT = Path(__file__).resolve().parents[1]
DESK_PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))

RECOVERY = {
    "manga-anime": {
        "id": "manga-anime-attack-on-titan-day-99-news-20260909",
        "desk": "manga-anime",
        "deskSlugs": ["manga-anime"],
        "section": "漫畫／動畫｜《進擊的巨人》",
        "status": "LATEST",
        "title": "9月9日首個「進擊的巨人之日」公布99項企劃　諫山創公開全新紀念插畫",
        "dek": "《進擊的巨人》官方為9月9日正式紀念日公布99項企劃，包括諫山創新繪、漫畫99話限時99小時免費，以及劇場版10月在日本以SCREENX、4DX等格式重映。",
        "summary": "《進擊的巨人》官方入口網站9月9日公開紀念日企劃；同日MANTANWEB報道，原作連載開始日獲正式認定為「進擊的巨人之日」，並一次公布99項相關消息。",
        "body": "《進擊的巨人》官方入口網站在9月9日首個正式「進擊的巨人之日」公開大型紀念企劃，包括集合九大巨人的紀念視覺、原作者諫山創全新插畫，以及官方YouTube頻道等內容。講談社旗下「Magazine Pocket」亦由9月9日起把原作首99話限時99小時免費公開。\n\nMANTANWEB同日凌晨報道，劇場版《進擊的巨人 前編～紅蓮的弓矢～》亦將於10月23日起在日本以SCREENX、4DX及ULTRA 4DX等格式重映。這些安排屬漫畫／動畫作品的當日正式企劃與發行消息，應只歸入漫畫／動畫版，不回流日本一般時政版。",
        "context": "《進擊的巨人》於2009年9月9日在講談社《別冊少年Magazine》創刊號開始連載；日本紀念日協會其後把9月9日正式認定為作品紀念日。",
        "why": "官方在紀念日當天一次公布新插畫、限時閱讀、影音頻道及劇場重映等實質安排，屬可即時更新漫畫／動畫版的有效新發展。",
        "watchNext": "留意9月9日晚間官方特別直播是否再公布動畫、遊戲或其他新企劃，以及10月劇場版重映的上映院線與後續票務安排。",
        "sourceName": "Attack on Titan Official Portal / MANTANWEB",
        "sourceUrl": "https://aot-portal.com/en/special/aotday2026/",
        "timeLabel": "9月9日00:00 JST報道；10:20 HKT核實",
        "publishedAt": "2026-09-09T00:00:00+09:00",
        "verifiedAt": "2026-09-09T10:20:00+08:00",
        "sources": [
            {"name": "Attack on Titan Official Portal", "url": "https://aot-portal.com/en/special/aotday2026/"},
            {"name": "MANTANWEB", "url": "https://mantan-web.jp/article/20260908dog00m200076000a.html"}
        ]
    },
    "japan": {
        "id": "japan-us-fx-policy-alignment-20260908",
        "desk": "japan",
        "deskSlugs": ["japan"],
        "section": "日本｜政策／匯率",
        "status": "LATEST",
        "title": "片山皋月稱日美匯率政策立場不變　日圓急升之際續就市場秩序保持溝通",
        "dek": "日本財務相表示，東京與華盛頓會繼續密切溝通，確保外匯市場有序運作；日圓近期因日本央行加息預期升至約七個月高位。",
        "summary": "日本財務相片山皋月9月8日表示，日美自7月底協調干預後對匯率政策的立場沒有改變，雙方將繼續就市場走勢保持密切聯絡。",
        "body": "Reuters於9月8日報道，日本財務相片山皋月在例行記者會表示，東京與華盛頓在外匯政策上的立場沒有改變，並會繼續與美國財政部保持密切溝通，以確保匯率市場有序運作。她亦提到近期曾在二十國集團會議等場合與美國財長Scott Bessent會談。\n\n日圓近期急升至約七個月高位，市場正在重新評估日本央行收緊政策的速度，以及日本投資者是否會把海外資金調回本土。今次表態顯示，即使匯率方向已由早前急跌轉為急升，日本政府仍關注波動本身而非單一價位。",
        "context": "日本與美國在2026年7月底曾協調行動支持日圓；市場其後轉向押注日本央行進一步加息，令匯率波動方向出現明顯逆轉。",
        "why": "這是日本財務相當日正式政策表態，涉及外匯市場秩序及日美政策協調，屬日本一般時政／經濟政策新聞，不應路由至其他專題版。",
        "watchNext": "留意日本央行9月17至18日會議、日圓波幅、財務省是否再就過度波動發出口頭警告，以及日美財金官員後續溝通。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/world/asia-pacific/japan-us-remain-aligned-fx-policy-foster-stable-markets-katayama-says-2026-09-08/",
        "timeLabel": "9月8日10:26 HKT報道",
        "publishedAt": "2026-09-08T10:26:00+08:00",
        "verifiedAt": "2026-09-08T18:18:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/world/asia-pacific/japan-us-remain-aligned-fx-policy-foster-stable-markets-katayama-says-2026-09-08/"}],
    },
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
    now = dt.datetime.now(HKT)
    changed = False

    for slug, story in RECOVERY.items():
        current = desks.setdefault(slug, [])
        sla = PUBLIC_DESK_FRESHNESS_HOURS[slug]
        age = newest_age_hours(current, now)
        if age <= sla:
            print(f"SPECIALIST_FRESHNESS_RECOVERY_SKIP slug={slug} age_h={age:.2f} sla_h={sla}")
            continue

        story_age = newest_age_hours([story], now)
        if story_age > sla:
            raise SystemExit(
                f"SPECIALIST_FRESHNESS_RECOVERY_STORY_STALE slug={slug} age_h={story_age:.2f} sla_h={sla}; refusing false repair"
            )

        story_id = story["id"]
        current[:] = [x for x in current if str(x.get("id") or "") != story_id]
        current.insert(0, story)
        changed = True
        print(f"SPECIALIST_FRESHNESS_RECOVERY_ADD slug={slug} age_h={age:.2f} id={story_id}")

    if changed:
        DESK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("SPECIALIST_FRESHNESS_RECOVERY_APPLIED")
    else:
        print("SPECIALIST_FRESHNESS_RECOVERY_NOOP")


if __name__ == "__main__":
    main()
