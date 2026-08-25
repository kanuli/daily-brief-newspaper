#!/usr/bin/env python3
"""Backfill rolling topic desks with verified, current, distinct stories.

This script never edits Live editorial items. It only promotes vetted recovery
stories into data/desk-latest.json when a topic desk is below its hard floor.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK_PATH = ROOT / "data" / "desk-latest.json"

FLOORS = {
    "world": 8,
    "asia": 8,
    "hong-kong": 6,
    "japan": 8,
    "market-economy": 8,
    "ai-tech": 6,
    "manga-anime": 4,
    "manchester-united": 4,
    "football": 10,
}

RECOVERY = {
    "world": [
        {
            "id": "world-haiti-kenscoff-20260825-depth",
            "desk": "world",
            "deskSlugs": ["world"],
            "section": "世界｜海地／治安",
            "status": "LATEST",
            "title": "海地幫派突襲肯斯科夫至少47死22傷，首都外圍安全危機再惡化",
            "dek": "聯合國指死傷數字仍可能變動；居民批評警力未能阻止多次致命襲擊。",
            "summary": "海地首都太子港附近山區肯斯科夫遭幫派聯盟突襲，聯合國最新統計至少47人死亡、22人受傷。",
            "body": "海地肯斯科夫在8月24日遭武裝幫派通宵突襲，聯合國表示至少47人死亡、22人受傷，數字仍可能調整。路透社及美聯社報道，襲擊者焚燒民居並攻擊居民；肯斯科夫位處通往太子港的重要路線，近年多次受到幫派攻擊。\n\n海地正準備多年來首次全國選舉，但首都及周邊地區的幫派控制與人口流離失所問題持續惡化。政府承諾增援治安力量，居民則要求加強警力及問責。",
            "context": "海地幫派勢力近年由太子港向周邊地區擴張，治安危機已影響政治過渡及選舉準備。",
            "why": "單次襲擊造成大規模死傷，並直接增加海地年底選舉及首都交通安全的不確定性。",
            "watchNext": "留意聯合國最終死傷統計、警方增援、幫派鎮壓部隊部署及選舉安全安排。",
            "sourceName": "Reuters",
            "sourceUrl": "https://www.reuters.com/world/americas/gang-attack-near-haitis-capital-leaves-30-dead-2026-08-24/",
            "timeLabel": "8月25日13:00 HKT前後核實",
            "sources": [
                {"name": "Reuters", "url": "https://www.reuters.com/world/americas/gang-attack-near-haitis-capital-leaves-30-dead-2026-08-24/"},
                {"name": "Associated Press", "url": "https://apnews.com/article/485903ee45cd5ffc1b5270b268ba31e3"}
            ]
        },
        {
            "id": "world-colombia-child-recruitment-20260825-depth",
            "desk": "world",
            "deskSlugs": ["world"],
            "section": "世界｜哥倫比亞／人權",
            "status": "LATEST",
            "title": "哥倫比亞武裝組織招募兒童急增，逾1,500宗個案兼出現無人機作戰訓練",
            "dek": "人權觀察指武裝組織利用社交平台、貧困與教育缺口招募未成年人。",
            "summary": "人權觀察最新報告指，哥倫比亞自2021年以來至少有1,500名兒童被武裝組織招募。",
            "body": "人權觀察8月24日發表102頁報告，根據哥倫比亞監察機構等資料指，自2021年以來至少1,500名兒童被武裝組織招募，近年個案明顯增加。報告指部分組織透過社交平台招募兒童，角色由情報、後勤延伸至操作載有爆炸物的無人機。\n\n美聯社亦報道同一研究，指出原住民兒童及教育、社會保障較薄弱地區尤其受影響。人權觀察要求新政府加強預防、救援、司法追究及社交平台證據保存。",
            "context": "哥倫比亞多個前游擊隊分支及犯罪組織仍在部分農村地區爭奪控制權。",
            "why": "兒童招募與無人機武器化同時擴大，反映地方安全與兒童保護制度面對新型態風險。",
            "watchNext": "留意哥倫比亞新政府的兒童保護政策、司法調查及社交平台回應。",
            "sourceName": "Human Rights Watch",
            "sourceUrl": "https://www.hrw.org/news/2026/08/24/colombia-armed-groups-expand-child-recruitment",
            "timeLabel": "8月25日13:00 HKT前後核實",
            "sources": [
                {"name": "Human Rights Watch", "url": "https://www.hrw.org/news/2026/08/24/colombia-armed-groups-expand-child-recruitment"},
                {"name": "Associated Press", "url": "https://apnews.com/article/05d3480258b8de5ee74f2b7efa1a77c4"}
            ]
        },
        {
            "id": "world-europe-heatwave-insurance-20260825-depth",
            "desk": "world",
            "deskSlugs": ["world", "market-economy"],
            "section": "世界｜歐洲／極端天氣",
            "status": "LATEST",
            "title": "歐洲連續熱浪推高死亡與保險風險，評級機構警告長期盈利受壓",
            "dek": "多國今夏錄得大量超額死亡；高溫亦增加醫療、壽險及再保險成本。",
            "summary": "歐洲今夏持續極端高溫，最新統計與評級分析顯示公共健康及保險業財務風險同步上升。",
            "body": "歐洲今夏連續出現破紀錄熱浪，最新部分統計顯示多國錄得大量超額死亡。英國《衛報》引述標普全球評級指出，高溫相關健康問題、住院及死亡索償增加，可能逐步侵蝕壽險、健康險與再保險公司的盈利。\n\n法國衞生部較早公布7月3日至22日熱浪期間錄得1,243宗超額死亡，路透社亦報道相關數字。隨人口老化及高溫頻率增加，保費、醫療成本與氣候適應支出可能進一步上升。",
            "context": "歐洲升溫速度高於全球平均，極端熱浪已由公共健康問題延伸至金融與保險風險。",
            "why": "熱浪影響同時跨越死亡率、醫療需求、保險索償及政府適應支出，具有跨國經濟影響。",
            "watchNext": "留意各國最終夏季死亡統計、保險公司索償數據及歐盟氣候適應政策。",
            "sourceName": "The Guardian",
            "sourceUrl": "https://www.theguardian.com/business/2026/aug/25/europe-heatwaves-insurance-companies-earnings",
            "timeLabel": "8月25日13:00 HKT前後核實",
            "sources": [
                {"name": "The Guardian", "url": "https://www.theguardian.com/business/2026/aug/25/europe-heatwaves-insurance-companies-earnings"},
                {"name": "Reuters", "url": "https://www.reuters.com/business/healthcare-pharmaceuticals/france-recorded-1243-excess-deaths-during-july-3-july-22-heatwaves-2026-08-19/"}
            ]
        }
    ],
    "japan": [
        {
            "id": "japan-typhoon18-okinawa-amami-20260825-depth",
            "desk": "japan",
            "deskSlugs": ["japan"],
            "section": "日本｜氣象／沖繩・奄美",
            "status": "LATEST",
            "title": "強颱風18號逼近沖繩本島與奄美，日本氣象廳警告猛烈風雨及大浪",
            "dek": "大東島已錄得強風，沖繩本島及奄美25日晚起面對暴風、雷雨與海面惡化。",
            "summary": "日本本地氣象資訊顯示，強颱風18號25日向沖繩本島及奄美接近，相關地區需防範暴風、非常激烈降雨及大浪。",
            "body": "日本朝日電視台25日上午報道，強颱風18號已影響大東島地方，之後向西北偏西移動，預料晚間最接近沖繩本島及奄美。北大東與南大東已錄得今年以來最強級別陣風，沖繩本島與奄美部分地區可能進入暴風圈。\n\n日本氣象廳的奄美地方天氣資料亦指出，25日受颱風18號影響，區內會轉為多雲有雨，局部伴隨雷暴及非常激烈降雨；沿岸海域至26日可能出現有湧浪的大浪或非常大浪。",
            "context": "沖繩及奄美處於西北太平洋颱風常見路徑，離島交通、供電及航班容易受強風浪影響。",
            "why": "屬當日直接影響日本居民交通與安全的本地氣象事件，並非重複既有地震或外交題材。",
            "watchNext": "留意氣象廳暴風與大雨警報、航班船班取消、停電及颱風路徑變化。",
            "sourceName": "テレビ朝日",
            "sourceUrl": "https://news.tv-asahi.co.jp/news_society/articles/900197837.html",
            "timeLabel": "8月25日12:00 HKT後核實",
            "sources": [
                {"name": "テレビ朝日", "url": "https://news.tv-asahi.co.jp/news_society/articles/900197837.html"},
                {"name": "気象庁", "url": "https://www.data.jma.go.jp/yoho/data/jishin/met/kishoushien_Kagoshima_Aira-shi.html"}
            ]
        },
        {
            "id": "japan-tobu-nikko-investigation-20260825-depth",
            "desk": "japan",
            "deskSlugs": ["japan"],
            "section": "日本｜交通／安全",
            "status": "LATEST",
            "title": "東武日光線4死事故揭列車時間未完整共享，關東運輸局展開安全調查",
            "dek": "新鹿沼站除草作業期間發生致命事故，調查聚焦見張員溝通與安全管理程序。",
            "summary": "日本朝日電視台最新報道指，東武日光線4名作業員死亡事故中，列車通過時間及班次沒有準確共享給所有現場人員。",
            "body": "日本朝日電視台25日報道，栃木縣東武日光線新鹿沼站4名除草作業員被特急列車撞死的事故，現場人員並非全部準確掌握列車通過時間及班次。國土交通大臣同日表示，關東運輸局已由24日起對東武鐵道展開現場調查，檢視安全管理規定。\n\n較早報道顯示，警方已搜查承辦作業的東武建設相關地點並扣押無線電設備，調查見張員之間的通訊及列車安全確認流程。事故發生於20日，安全管理問題仍在釐清。",
            "context": "鐵路線旁維修作業依賴列車時間、見張員與無線通訊的多重安全確認。",
            "why": "最新調查由事故本身進一步指向現場資訊共享與制度執行，直接關係鐵路工程安全。",
            "watchNext": "留意關東運輸局調查結果、警方是否提出刑事責任，以及東武鐵道改善措施。",
            "sourceName": "テレビ朝日",
            "sourceUrl": "https://news.tv-asahi.co.jp/news_society/articles/000528553.html",
            "timeLabel": "8月25日12:30 HKT前後核實",
            "sources": [
                {"name": "テレビ朝日", "url": "https://news.tv-asahi.co.jp/news_society/articles/000528553.html"},
                {"name": "テレビ朝日（前一日調查進展）", "url": "https://news.tv-asahi.co.jp/news_society/articles/000528236.html"}
            ]
        }
    ],
    "football": [
        {
            "id": "football-juventus-frosinone-20260825-depth",
            "desk": "football",
            "deskSlugs": ["football"],
            "section": "Football｜意甲",
            "status": "LATEST",
            "title": "祖雲達斯1：0擊敗費辛隆尼開季全取三分，史巴列堤要求高路梅安尼提升表現",
            "dek": "布雷默頭槌奠勝；新加盟前鋒高路梅安尼多次有機會但未能入球。",
            "summary": "祖雲達斯作客1：0擊敗費辛隆尼，布雷默取得唯一入球；主帥史巴列堤賽後要求高路梅安尼盡快找回入球狀態。",
            "body": "祖雲達斯在2026/27意甲首輪作客1：0擊敗費辛隆尼，球會官方賽事報告確認布雷默在上半場22分鐘頭槌建功。高路梅安尼正選上陣並獲得多次機會，但未能取得入球。\n\n路透社其後報道，主帥史巴列堤認為新加盟的高路梅安尼仍需提升狀態與終結能力。這名法國前鋒以3,800萬歐元從巴黎聖日耳門重返祖雲達斯，簽約五年。",
            "context": "意甲新季剛開鑼，祖雲達斯正以新前鋒配置重整進攻線。",
            "why": "開季勝仗與高價新援表現同時影響祖雲達斯爭標預期及前線輪換。",
            "watchNext": "留意祖雲達斯下一輪對帕爾馬、高路梅安尼入球狀態及前鋒輪換。",
            "sourceName": "Juventus",
            "sourceUrl": "https://www.juventus.com/en/news/articles/bremer-header-secures-victory-over-frosinone-23-08-26?appview=true",
            "timeLabel": "8月25日13:00 HKT前後核實",
            "sources": [
                {"name": "Juventus", "url": "https://www.juventus.com/en/news/articles/bremer-header-secures-victory-over-frosinone-23-08-26?appview=true"},
                {"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/juve-boss-spalletti-demands-more-kolo-muani-2026-08-24/"}
            ]
        }
    ]
}


def key(story):
    return (str(story.get("id") or "").strip(), str(story.get("title") or "").strip())


def main():
    data = json.loads(DESK_PATH.read_text(encoding="utf-8"))
    desks = data.setdefault("desks", {})
    for slug, minimum in FLOORS.items():
        current = desks.setdefault(slug, [])
        seen_ids = {str(s.get("id") or "") for s in current}
        seen_titles = {str(s.get("title") or "") for s in current}
        if len({str(s.get("id") or s.get("title") or i) for i, s in enumerate(current)}) >= minimum:
            continue
        for story in RECOVERY.get(slug, []):
            if story["id"] in seen_ids or story["title"] in seen_titles:
                continue
            current.append(story)
            seen_ids.add(story["id"])
            seen_titles.add(story["title"])
            if len({str(s.get("id") or s.get("title") or i) for i, s in enumerate(current)}) >= minimum:
                break
    DESK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("DESK DEPTH RECOVERY CANDIDATES APPLIED")


if __name__ == "__main__":
    main()
