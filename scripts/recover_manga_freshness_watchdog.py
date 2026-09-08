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
        "sources": [{"name": "MANTANWEB", "url": "https://en.mantan-web.jp/e_article/20260907dog00m200073000a.html"}],
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
