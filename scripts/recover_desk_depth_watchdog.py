#!/usr/bin/env python3
"""Watchdog-safe desk-depth recovery with current same-event groupings.

This wrapper preserves the existing vetted recovery inventory and adds event
aliases and independently verified current stories discovered by the
publication watchdog. It never edits Live items.
"""
import json

import recover_desk_depth as base

# These are two editorial updates of the same Canada/U.S. tariff dispute, not
# two independent World events. Count them once for topic-depth purposes.
base.EVENT_GROUPS.update({
    "world-canada-auto-tariff-20260825": "world-canada-us-tariffs-20260824",
    "world-canada-us-tariffs-20260824-1000": "world-canada-us-tariffs-20260824",
})

# Fresh distinct World event verified on 25 Aug 2026. Reuters reports Chancellor
# Friedrich Merz said Germany would soon identify who was behind the attempted
# drone attack at Leipzig/Halle airport; Euronews independently reported German
# investigators found a third drone and suspected explosives at the airport.
base.RECOVERY.setdefault("world", []).insert(0, {
    "id": "world-germany-leipzig-drone-20260825-depth",
    "desk": "world",
    "deskSlugs": ["world"],
    "section": "世界｜德國／安全",
    "status": "LATEST",
    "title": "德國調查萊比錫／哈雷機場無人機事件，政府稱將公布幕後責任方",
    "dek": "德國調查人員在機場附近再發現無人機及疑似爆炸物；總理默茨稱當局將很快交代責任方。",
    "summary": "德國總理默茨表示，政府將很快公布本月萊比錫／哈雷機場企圖無人機襲擊的責任方；歐洲新聞台同日報道，調查人員再發現第三架無人機及疑似爆炸物。",
    "body": "德國總理默茨8月25日表示，政府將很快公布本月萊比錫／哈雷機場企圖無人機襲擊的責任方。該機場是德國及北約軍事物資運輸的重要節點，亦供烏克蘭安托諾夫航空使用。\n\n歐洲新聞台同日報道，德國調查人員在機場一帶再發現第三架無人機及疑似爆炸物。事件把歐洲關鍵運輸基建的無人機防護與反破壞能力再次推上安全議程。",
    "context": "歐洲多國近年加強機場、港口及軍民兩用基建的無人機監測與反制措施。",
    "why": "事件涉及德國關鍵航空物流、北約運輸節點及歐洲基建安全，屬與其他 World retained stories 不同的獨立發展。",
    "watchNext": "留意德國當局公布責任方、調查是否涉及外國勢力，以及機場安全措施是否升級。",
    "sourceName": "Reuters",
    "sourceUrl": "https://quews.news/germany-to-say-whos/",
    "timeLabel": "8月25日20:00 HKT前核實",
    "sources": [
        {"name": "Reuters", "url": "https://quews.news/germany-to-say-whos/"},
        {"name": "Euronews", "url": "https://www.euronews.com/2026/08/25"}
    ]
})

# Manchester United is a lower-volume topic desk, but its depth still uses a
# current roughly-48-hour window. These older 25 Aug recovery items must not be
# the entries that keep the desk above its floor on 28 Aug.
STALE_MU_IDS = {
    "mu-hull-fallout-20260825",
    "mu-wheatley-lincoln-loan-20260825-depth",
    "mu-ipswich-preview-20260825-depth",
    "mu-devaney-hibernian-loan-20260825-depth",
}

# Two distinct current developments verified on 28 Aug 2026. They are separate
# from the Baleba signing and the Champions League draw already retained.
current_mu = [
    {
        "id": "mu-ipswich-team-news-20260828-depth",
        "desk": "manchester-united",
        "deskSlugs": ["manchester-united"],
        "section": "Manchester United｜英超／賽前",
        "status": "LATEST",
        "title": "曼聯鬥葉士域治前更新傷兵，阿密特與巴利巴缺陣、曼治恢復操練",
        "dek": "卡域克確認阿密特仍要休戰，新加盟巴利巴因足踝問題未能上陣；曼治本周已重返球隊操練。",
        "summary": "曼聯主帥卡域克在8月28日賽前記者會確認，阿密特迪亞路及卡路士巴利巴不會出戰葉士域治，曼治則已恢復跟隊訓練。",
        "body": "曼聯主帥米高卡域克8月28日在對葉士域治的英超賽前記者會更新陣容情況，確認阿密特迪亞路仍未能復出；新加盟的卡路士巴利巴亦因足踝問題需要多休息約兩至三周。\n\n較正面的消息是曼治已在本周恢復跟隊訓練。曼聯首輪作客侯城以0：2落敗，今輪返回奧脫福需要改善進攻效率，最新傷兵狀況亦直接影響卡域克的正選選擇。",
        "context": "曼聯新季首戰失利，而巴利巴剛完成轉會，球隊正準備8月30日主場對葉士域治。",
        "why": "屬比賽前兩日公布的最新一隊傷兵與復操資料，直接影響下一輪英超排陣。",
        "watchNext": "留意8月30日正選名單、曼治是否復出，以及巴利巴與阿密特的康復時間表。",
        "sourceName": "The Guardian",
        "sourceUrl": "https://www.theguardian.com/football/live/2026/aug/28/transfer-latest-premier-league-news-european-draws-and-more-football-live",
        "timeLabel": "28 Aug 2026 · 賽前記者會",
        "sources": [
            {"name": "The Guardian", "url": "https://www.theguardian.com/football/live/2026/aug/28/transfer-latest-premier-league-news-european-draws-and-more-football-live"},
            {"name": "Evening Standard via Yahoo Sports", "url": "https://sports.yahoo.com/articles/manchester-united-xi-vs-ipswich-101638794.html"}
        ]
    },
    {
        "id": "mu-league-cup-brighton-draw-20260828-depth",
        "desk": "manchester-united",
        "deskSlugs": ["manchester-united"],
        "section": "Manchester United｜聯賽盃",
        "status": "LATEST",
        "title": "曼聯聯賽盃第三圈主場對白禮頓，賽事安排於9月上半月",
        "dek": "曼聯因參加歐洲賽事由第三圈加入，抽籤結果要在奧脫福迎戰同屬英超的白禮頓。",
        "summary": "英格蘭聯賽盃第三圈抽籤確認，曼聯將主場迎戰白禮頓，賽事安排在9月7日或14日開始的其中一周舉行。",
        "body": "英格蘭聯賽盃第三圈抽籤完成，今季重返歐洲賽場的曼聯由此圈加入，抽中在奧脫福迎戰白禮頓。路透社與《衛報》的第三圈抽籤報道均列出這場全英超對碰。\n\n第三圈賽程分散在9月7日及14日開始的兩個比賽周，以配合歐洲賽事。對曼聯而言，這是今季首個本土盃賽淘汰賽對手，亦與較早公布的歐聯聯賽階段抽籤屬兩個不同賽事發展。",
        "context": "參加歐洲賽事的英超球隊今季在聯賽盃第三圈加入。",
        "why": "已確認的本土盃賽對手會直接影響9月賽程與輪換安排，屬獨立於歐聯抽籤的曼聯新聞。",
        "watchNext": "留意英格蘭足球聯賽公布確實開賽日期與轉播安排，以及卡域克的盃賽輪換。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/sports/soccer/spurs-win-big-then-draw-liverpool-league-cup-2026-08-26/",
        "timeLabel": "27–28 Aug 2026 · 抽籤確認",
        "sources": [
            {"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/spurs-win-big-then-draw-liverpool-league-cup-2026-08-26/"},
            {"name": "The Guardian", "url": "https://www.theguardian.com/football/live/2026/aug/26/newcastle-v-west-brom-tottenham-v-charlton-preston-v-everton-carabao-cup-live"}
        ]
    },
]
for story in reversed(current_mu):
    base.RECOVERY.setdefault("manchester-united", []).insert(0, story)


def _drop_expired_mu_items():
    data = json.loads(base.DESK_PATH.read_text(encoding="utf-8"))
    desks = data.setdefault("desks", {})
    current = desks.setdefault("manchester-united", [])
    filtered = [story for story in current if str(story.get("id") or "") not in STALE_MU_IDS]
    if len(filtered) != len(current):
        desks["manchester-united"] = filtered
        base.DESK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"MU_48H_RETENTION_PRUNE removed={len(current)-len(filtered)}")


if __name__ == "__main__":
    _drop_expired_mu_items()
    base.main()
