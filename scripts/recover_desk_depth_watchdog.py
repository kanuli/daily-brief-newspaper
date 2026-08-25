#!/usr/bin/env python3
"""Watchdog-safe desk-depth recovery with current same-event groupings.

This wrapper preserves the existing vetted recovery inventory and adds event
aliases and independently verified current stories discovered by the
publication watchdog. It never edits Live items.
"""
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
    "why": "事件涉及德國關鍵航空物流、北約運輸節點及歐洲基建安全，屬與其他World retained stories不同的獨立發展。",
    "watchNext": "留意德國當局公布責任方、調查是否涉及外國勢力，以及機場安全措施是否升級。",
    "sourceName": "Reuters",
    "sourceUrl": "https://quews.news/germany-to-say-whos/",
    "timeLabel": "8月25日20:00 HKT前核實",
    "sources": [
        {"name": "Reuters", "url": "https://quews.news/germany-to-say-whos/"},
        {"name": "Euronews", "url": "https://www.euronews.com/2026/08/25"}
    ]
})

if __name__ == "__main__":
    base.main()
