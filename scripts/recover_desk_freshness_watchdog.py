#!/usr/bin/env python3
"""Editor-in-Chief freshness recovery for verified topic-desk events.

This helper is publication-only: it never creates a Live edition. It adds
editorially vetted, current events to stale desks before the existing
freshness/publication validators run. Same IDs are idempotent across retries.
A recovery template must itself satisfy the desk freshness SLA; otherwise the
watchdog fails rather than falsely claiming that stale content repaired a desk.
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
        "id": "world-ukraine-prosecutor-general-resignation-20260908",
        "desk": "world",
        "deskSlugs": ["world"],
        "section": "世界｜歐洲／烏克蘭政治",
        "status": "LATEST",
        "title": "烏克蘭總檢察長提出辭職　稱不願職位成政治對抗工具",
        "dek": "Ruslan Kravchenko表示辭職屬政治決定，要求總統澤連斯基及國會接納；事件正值烏克蘭高層接連出現人事變動。",
        "summary": "烏克蘭總檢察長Ruslan Kravchenko提出辭職，稱不希望總檢察長職位被用作政治對抗工具；他同時重申否認涉及檢察機關近期被揭發的詐騙犯罪組織。",
        "body": "路透社9月8日報道，烏克蘭總檢察長Ruslan Kravchenko表示已提出辭職，形容這是自己有意識作出的政治決定，並要求總統澤連斯基及最高拉達接納。他表示不希望總檢察長職位被用作政治對抗工具，但沒有進一步說明辭職背後的具體政治爭議。\n\n烏克蘭反貪機構NABU及SAPO上周表示，已揭發一個涉及詐騙呼叫中心的犯罪組織，據稱由總檢察長辦公室一名官員安排。Kravchenko否認自己涉及相關指控。今次辭職要求延續烏克蘭政府高層近期的人事變動，時間上亦正值俄烏戰爭持續。",
        "context": "烏克蘭在戰時同時面對反貪、政府管治與軍事壓力；高層司法及行政人事變動會影響政府內部穩定與改革可信度。",
        "why": "總檢察長在戰時提出辭職並明言涉及政治對抗，是烏克蘭政府高層的重要政治與司法發展，屬非亞洲World版新聞。",
        "watchNext": "留意澤連斯基及最高拉達會否接納辭呈、總檢察長職位繼任安排，以及反貪機構調查是否牽涉更多高層官員。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/business/aerospace-defense/ukraines-prosecutor-general-submits-resignation-citing-political-conflict-2026-09-08/",
        "timeLabel": "9月8日08:14 HKT報道",
        "publishedAt": "2026-09-08T08:14:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/business/aerospace-defense/ukraines-prosecutor-general-submits-resignation-citing-political-conflict-2026-09-08/"}],
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
        "id": "football-como-picchi-contract-cancer-20260908",
        "desk": "football",
        "deskSlugs": ["football"],
        "section": "Football｜女子足球／意大利",
        "status": "LATEST",
        "title": "Como與前鋒Roberta Picchi續約至2028年　球員確診乳癌接受治療",
        "dek": "意大利女子足球球會Como宣布與34歲前鋒Roberta Picchi續約至2027/28球季結束，球會醫療團隊將在她接受乳癌治療期間提供支援。",
        "summary": "Como在Roberta Picchi確診乳癌後與她延長合約，並表示會由球會醫療團隊配合專科醫生支援其治療及康復。",
        "body": "Reuters於9月8日報道，Como已把34歲前鋒Roberta Picchi的合約延長至2027/28球季結束。球會表示，Picchi確診乳癌後，醫療團隊會與負責她治療的專科醫生密切合作，並在未來數月提供支援。\n\nPicchi透過社交平台感謝球會，表示自己會專注接受治療，並希望之後以更堅定的狀態回歸。球會同時要求外界尊重球員及其家人的私隱。",
        "context": "這是女子足球球員健康與合約安排的正式球會決定，涉及Como對球員治療期間的醫療與職業保障。",
        "why": "事件屬意大利女子足球的即時球員與球會發展，符合全球Football版涵蓋女子足球、球員狀況及合約消息的路由規則。",
        "watchNext": "留意Picchi治療及康復進展、Como後續球員安排，以及她何時能恢復足球活動。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/sports/soccer/como-renews-picchis-contract-after-cancer-diagnosis-2026-09-08/",
        "timeLabel": "9月8日12:31 HKT報道",
        "publishedAt": "2026-09-08T12:31:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/como-renews-picchis-contract-after-cancer-diagnosis-2026-09-08/"}],
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

        template_age = newest_age_hours([template], now)
        if template_age > sla:
            raise SystemExit(
                f"DESK_FRESHNESS_RECOVERY_TEMPLATE_STALE slug={slug} template_age_h={template_age:.2f} sla_h={sla}; refusing false repair"
            )

        story = copy.deepcopy(template)
        story_id = str(story["id"])
        current[:] = [x for x in current if str(x.get("id") or "") != story_id]
        current.insert(0, story)
        changed = True
        print(f"DESK_FRESHNESS_RECOVERY_ADD slug={slug} age_h={age:.2f} id={story_id}")

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