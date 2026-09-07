#!/usr/bin/env python3
"""Editor-in-Chief freshness recovery for verified topic-desk events.

This helper is publication-only: it never creates a Live edition.  It adds
editorially vetted, current events to stale desks before the existing
freshness/publication validators run. Same IDs are idempotent across retries.
"""
import copy
import datetime as dt
import json
from pathlib import Path

from desk_freshness_policy import PUBLIC_DESK_FRESHNESS_HOURS, editorial_story_time, routed_slugs

ROOT = Path(__file__).resolve().parents[1]
DESK_PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))

RECOVERY = {
    "world": {
        "id": "world-us-canada-bombardier-trump-sales-20260908",
        "desk": "world",
        "deskSlugs": ["world"],
        "section": "世界｜美加貿易／航空",
        "status": "LATEST",
        "title": "特朗普稱Bombardier若不在美國生產　將不准在美銷售飛機",
        "dek": "特朗普在Truth Social表示，加拿大飛機製造商Bombardier若要繼續進入美國市場，必須在美國生產；具體執行機制仍未公布。",
        "summary": "美國總統特朗普表示，除非Bombardier把生產移到美國，否則將不准該公司在美國銷售飛機。事件令美加貿易摩擦延伸至高度整合的航空產業。",
        "body": "路透社9月7日報道，美國總統特朗普在Truth Social發文，稱加拿大私人飛機製造商Bombardier若要繼續在美國市場銷售飛機，就必須在美國生產。他未交代政府會用甚麼法律或監管工具執行有關要求；白宮當時亦未回覆路透查詢。\n\nBombardier的飛機已獲美國聯邦航空管理局批准，公司在美國約有3,500名員工，供應鏈亦與美國航空業高度整合。加拿大正準備對美國實施新一輪反制關稅，今次表態令航空製造業成為兩國貿易摩擦的新焦點。",
        "context": "美國與加拿大近期貿易摩擦升溫；航空業跨境供應鏈高度整合，任何銷售限制都可能牽動製造商、供應商與企業飛機客戶。",
        "why": "這是美國總統針對加拿大主要航空製造商的直接政策威脅，涉及跨境貿易與航空產業准入，主要新聞價值屬非亞洲國際政經發展。",
        "watchNext": "留意白宮、FAA或其他美國部門會否提出正式執行措施，以及加拿大政府與Bombardier的回應。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/business/aerospace-defense/trump-says-canadas-bombardier-cannot-sell-us-unless-it-builds-there-2026-09-07/",
        "timeLabel": "9月8日01:51 HKT報道",
        "publishedAt": "2026-09-08T01:51:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/business/aerospace-defense/trump-says-canadas-bombardier-cannot-sell-us-unless-it-builds-there-2026-09-07/"}],
    },
    "hong-kong": {
        "id": "hong-kong-hko-mainly-fine-hot-20260908-0402",
        "desk": "hong-kong",
        "deskSlugs": ["hong-kong"],
        "section": "香港｜天氣",
        "status": "LATEST",
        "title": "天文台清晨錄得28度　今日主要天晴兼日間酷熱",
        "dek": "天文台凌晨4時02分更新實況，錄得氣溫28度、相對濕度86%；今日紫外線指數預測約9，屬甚高水平。",
        "summary": "香港天文台9月8日清晨更新天氣資料，市區氣溫約28度；最新預報指今日主要天晴並在日間酷熱，市民外出需留意高溫及紫外線。",
        "body": "香港天文台在9月8日凌晨4時02分更新天氣實況，天文台錄得氣溫28度、相對濕度86%，天氣圖示為主要天晴；多區氣溫介乎約24至28度。\n\n天文台另預測9月8日最高紫外線指數約9，強度屬甚高。高溫天氣可能影響健康，長時間戶外活動人士應補充水分並採取防曬措施。",
        "context": "9月初香港仍處炎熱季節，天文台持續發布高溫及紫外線資訊，相關更新直接影響市民日常出行與戶外活動安排。",
        "why": "這是香港官方氣象部門的即時公共資訊，具有直接本地生活及健康影響。",
        "watchNext": "留意天文台日間氣溫、驟雨及雷暴更新，以及是否發出任何高溫或惡劣天氣提示。",
        "sourceName": "香港天文台",
        "sourceUrl": "https://www.hko.gov.hk/hko/textonly/v2/forecast/englishwx2.htm",
        "timeLabel": "9月8日04:02 HKT更新",
        "publishedAt": "2026-09-08T04:02:00+08:00",
        "sources": [{"name": "香港天文台", "url": "https://www.hko.gov.hk/hko/textonly/v2/forecast/englishwx2.htm"}],
    },
    "market-economy": {
        "id": "market-economy-poste-tim-offer-raised-20260908",
        "desk": "market-economy",
        "deskSlugs": ["market-economy"],
        "section": "財經／市場｜企業併購",
        "status": "LATEST",
        "title": "Poste Italiane提高收購Telecom Italia出價　總值增至113.5億歐元",
        "dek": "Poste Italiane把收購Telecom Italia的出價提高5.5億歐元，並首次加入股份對價，同時撤銷須取得66.67%股份的成交門檻。",
        "summary": "意大利國營背景金融集團Poste Italiane提高對Telecom Italia的收購條件，總估值增至113.5億歐元，反映競購進入關鍵階段。",
        "body": "路透社9月7日報道，Poste Italiane把收購Telecom Italia的出價提高5.5億歐元至113.5億歐元。新方案把每股現金部分提高0.30歐元至1.97歐元，並首次加入每股Telecom Italia換取0.218股新發Poste股份的安排。\n\nPoste同時撤銷原先要求取得至少66.67%流通股份的條件。路透按市場資料計算，Poste在原有20%持股以外，目前透過要約取得的額外股份約5%；要約期本周五結束，並將在9月21日至25日重新開放。",
        "context": "Poste今年3月提出收購Telecom Italia，目標是建立意大利數碼基建與服務的國家級企業。",
        "why": "收購價、現金與股份組合及最低接納門檻均有重大改動，直接影響Telecom Italia估值及交易完成概率。",
        "watchNext": "留意本周五首輪要約截止時的接納比例，以及9月21日至25日重開期間是否再有條件調整。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/business/poste-italiane-raises-telecom-italia-offer-waives-threshold-condition-2026-09-07/",
        "timeLabel": "9月8日04:15 HKT報道",
        "publishedAt": "2026-09-08T04:15:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/business/poste-italiane-raises-telecom-italia-offer-waives-threshold-condition-2026-09-07/"}],
    },
    "ai-tech": {
        "id": "ai-tech-europe-satellite-direct-to-mobile-consortium-20260908",
        "desk": "ai-tech",
        "deskSlugs": ["ai-tech"],
        "section": "AI／科技｜衛星通訊",
        "status": "LATEST",
        "title": "歐洲四大電訊商據報商討組聯盟　競投歐盟衛星直連手機頻譜",
        "dek": "彭博引述知情人士指Deutsche Telekom、Orange、Vodafone及Telefónica正初步商討合作，路透其後轉述；各方尚未作最終決定。",
        "summary": "歐洲主要流動通訊商據報研究組成聯盟，競投歐盟預留給歐洲營運商的衛星頻譜，以發展衛星直接連接手機服務。",
        "body": "路透社9月7日轉述彭博報道，Deutsche Telekom、Orange、Vodafone及Telefónica正進行初步磋商，研究組成聯盟競投歐盟衛星頻譜，並提供衛星直接連接手機服務。彭博稱，聯盟可能競投歐盟擬預留給本地營運商的2 GHz頻段，但目前未有最終決定。\n\n歐盟今年5月公布衛星頻譜分配方向，計劃把更多容量留給歐洲企業，以提升自主衛星能力並減少對美國營運商的依賴。Vodafone、Orange及Telefónica拒絕向路透評論，Deutsche Telekom當時未即時回覆。",
        "context": "歐盟正推動IRIS²多軌道衛星網絡及通訊自主化，衛星直連手機已成為電訊商與衛星企業的新競爭領域。",
        "why": "若聯盟成形，將直接影響歐洲衛星頻譜競投、直連手機技術部署及區內通訊自主政策。",
        "watchNext": "留意四家公司是否正式確認聯盟、歐盟頻譜招標條款，以及IRIS²商用容量的分配時間表。",
        "sourceName": "Reuters／Bloomberg",
        "sourceUrl": "https://www.reuters.com/business/media-telecom/europes-biggest-mobile-operators-talks-satellite-to-mobile-venture-bloomberg-2026-09-07/",
        "timeLabel": "9月8日01:44 HKT報道",
        "publishedAt": "2026-09-08T01:44:00+08:00",
        "sources": [{"name": "Reuters（轉述Bloomberg）", "url": "https://www.reuters.com/business/media-telecom/europes-biggest-mobile-operators-talks-satellite-to-mobile-venture-bloomberg-2026-09-07/"}],
    },
    "manchester-united": {
        "id": "manchester-united-sabah-champions-league-preview-20260908",
        "desk": "manchester-united",
        "deskSlugs": ["manchester-united", "football"],
        "section": "Manchester United｜歐聯",
        "status": "LATEST",
        "title": "曼聯官網發布對Sabah歐聯賽前指南　奧脫福特迎接下一場歐洲賽",
        "dek": "曼聯官網最新賽前指南列出對Sabah的歐聯賽事及收看資訊；球隊在2比2賽和愛華頓後轉入歐洲賽備戰。",
        "summary": "曼聯官方網站更新對Sabah的歐聯賽前資訊，確認下一場賽事在奧脫福特舉行，並整理球迷的轉播及跟進方法。",
        "body": "曼聯官方網站9月8日清晨顯示，球會已發布對Sabah的歐聯賽前指南，介紹賽事跟進及收看方法；官網賽程亦把Man Utd對Sabah列為下一場歐聯賽事，地點為奧脫福特。\n\n曼聯上一場英超作客愛華頓踢成2比2，今次更新標誌球隊注意力已轉向歐洲賽。由於屬曼聯本身的足球賽事資訊，文章同時歸入Manchester United及Football版。",
        "context": "曼聯在英超開季三場後轉入歐聯賽程，對Sabah一戰是球隊近期重要主場歐洲賽。",
        "why": "這是球會官方最新賽前資訊，直接關乎曼聯下一場正式比賽及球迷收看安排。",
        "watchNext": "留意曼聯公布比賽日大軍、傷兵更新、正選陣容及賽前記者會內容。",
        "sourceName": "Manchester United",
        "sourceUrl": "https://www.manutd.com/en/news/how-to-watch-and-follow-united-v-sabah-champions-league",
        "timeLabel": "9月8日清晨核實（曼聯官網顯示約7小時前發布）",
        "verifiedAt": "2026-09-08T06:10:00+08:00",
        "sources": [{"name": "Manchester United", "url": "https://www.manutd.com/en/news/how-to-watch-and-follow-united-v-sabah-champions-league"}],
    },
    "football": {
        "id": "football-kansas-city-current-andonovski-departure-20260908",
        "desk": "football",
        "deskSlugs": ["football"],
        "section": "Football｜女子足球／NWSL",
        "status": "LATEST",
        "title": "Kansas City Current與體育總監Andonovski分道揚鑣",
        "dek": "NWSL球會Kansas City Current宣布與Vlatko Andonovski共同決定結束合作；他去年由主教練轉任體育總監。",
        "summary": "Kansas City Current與前美國女足主帥Vlatko Andonovski結束合作，球會表示雙方認為由教練轉任體育總監的安排並不合適。",
        "body": "Kansas City Current在9月7日宣布，球會與體育總監Vlatko Andonovski共同決定分道揚鑣。球會表示，雙方認為他在上季結束後由教練轉任體育總監的安排並不合適。\n\nAndonovski在2023年10月出任Kansas City Current主教練，帶隊贏得2025年NWSL Shield，其後轉任管理層，由Chris Armas接任主教練。他亦曾在2019至2023年執教美國女子國家隊。",
        "context": "Kansas City Current近年是NWSL主要競爭者之一；體育總監變動會影響球員招聘、陣容規劃及長期競技方向。",
        "why": "這是女子足球頂級聯賽球會的正式管理層變動，屬全球Football版的實質新聞。",
        "watchNext": "留意Kansas City Current如何重組足球管理層，以及Andonovski下一步去向。",
        "sourceName": "Kansas City Current／Reuters",
        "sourceUrl": "https://www.kansascitycurrent.com/news/press",
        "timeLabel": "9月8日01:09 HKT前後公布／報道",
        "publishedAt": "2026-09-08T01:09:00+08:00",
        "sources": [
            {"name": "Kansas City Current", "url": "https://www.kansascitycurrent.com/news/press"},
            {"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/current-part-ways-with-sporting-director-vlatko-andonovski--flm-2026-09-07/"}
        ],
    },
}


def newest_age_hours(stories, now):
    stamps = []
    for story in stories:
        if isinstance(story, dict):
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

    for slug, template in RECOVERY.items():
        current = desks.setdefault(slug, [])
        age = newest_age_hours(current, now)
        sla = PUBLIC_DESK_FRESHNESS_HOURS[slug]
        if age <= sla:
            print(f"DESK_FRESHNESS_RECOVERY_SKIP slug={slug} age_h={age:.2f} sla_h={sla}")
            continue

        story = copy.deepcopy(template)
        story_id = str(story["id"])
        current[:] = [x for x in current if str(x.get("id") or "") != story_id]
        current.insert(0, story)
        changed = True
        print(f"DESK_FRESHNESS_RECOVERY_ADD slug={slug} age_h={age:.2f} id={story_id}")

        # Manchester United-specific football must appear on both the dedicated
        # MU page and the general Football page. Preserve the same ID/source.
        routes = routed_slugs(story)
        for route in routes:
            if route == slug or route not in desks:
                continue
            routed = desks.setdefault(route, [])
            routed[:] = [x for x in routed if str(x.get("id") or "") != story_id]
            routed.insert(0, copy.deepcopy(story))
            print(f"DESK_FRESHNESS_RECOVERY_CROSS_ROUTE id={story_id} route={route}")

    if changed:
        DESK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("DESK_FRESHNESS_RECOVERY_APPLIED")
    else:
        print("DESK_FRESHNESS_RECOVERY_NOOP")


if __name__ == "__main__":
    main()
