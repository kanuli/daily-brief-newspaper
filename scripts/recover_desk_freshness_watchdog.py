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
        "id": "hong-kong-hko-very-hot-warning-20260908-1402",
        "desk": "hong-kong",
        "deskSlugs": ["hong-kong"],
        "section": "香港｜天氣／酷熱",
        "status": "LATEST",
        "title": "天文台下午錄得31度　酷熱天氣警告持續生效",
        "dek": "天文台下午2時02分更新本港天氣，總部錄得31度、相對濕度68%；元朗公園達35度，酷熱天氣警告仍然生效。",
        "summary": "香港天文台9月8日下午更新天氣資料，市區氣溫31度，多區達33度或以上；酷熱天氣警告持續生效，市民應慎防中暑並補充水分。",
        "body": "香港天文台在9月8日下午2時02分發出最新每小時溫度濕度報告，下午2時天文台錄得31度、相對濕度68%；元朗公園錄得35度，打鼓嶺、流浮山、大埔、沙田、屯門、將軍澳、西貢、石崗、黃大仙等多區錄得33度。\n\n酷熱天氣警告當時仍然生效，天文台提醒市民慎防中暑並多補充水分。過去一小時京士柏平均紫外線指數為4，強度屬中等。高溫在午後持續，戶外工作及活動人士尤其需要留意熱壓力。",
        "context": "香港9月初仍受炎熱天氣影響；高溫警告直接關乎戶外工作、長者與慢性病患者，以及市民日常出行安排。",
        "why": "這是香港天文台當日下午的官方本地公共安全資訊，酷熱警告及多區高溫對健康和戶外活動有即時影響。",
        "watchNext": "留意天文台稍後氣溫、驟雨及雷暴更新，以及酷熱天氣警告何時取消。",
        "sourceName": "香港天文台／政府新聞處",
        "sourceUrl": "https://www.info.gov.hk/gia/wr/202609/08/P2026090800377.htm",
        "timeLabel": "9月8日14:02 HKT更新",
        "publishedAt": "2026-09-08T14:02:00+08:00",
        "sources": [{"name": "香港天文台／政府新聞處", "url": "https://www.info.gov.hk/gia/wr/202609/08/P2026090800377.htm"}],
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
        "id": "ai-tech-mistral-series-d-20260908",
        "desk": "ai-tech",
        "deskSlugs": ["ai-tech"],
        "section": "AI／科技｜人工智能／融資",
        "status": "LATEST",
        "title": "Mistral完成30億歐元融資　估值升至約210億歐元",
        "dek": "法國AI公司Mistral完成30億歐元融資，Samsung、Scaleup Europe Fund及PSG Equity共同領投；公司表示資金將用於模型、算力與前沿研究。",
        "summary": "Mistral完成歐洲私人科技企業歷來最大規模之一的股權融資，估值升至約210億歐元，進一步擴充歐洲自主AI模型及基建能力。",
        "body": "路透社9月8日報道，法國人工智能公司Mistral完成30億歐元融資，公司估值約210億歐元。今輪由現有投資者PSG Equity、Samsung Electronics及歐盟支持的Scaleup Europe Fund共同領投；Samsung與Scaleup Europe Fund都是首次投資Mistral。\n\nMistral財務總監Johan Bergqvist表示，新資金會用於提升模型能力及投資前沿研究。公司目前有超過125家客戶，並預計今年底年度經常性收入達10億美元。Mistral亦把自身定位為歐洲可自主控制模型、數據及算力的重要AI供應商。",
        "context": "歐洲正加快建立自主AI模型與運算基建，以降低對美國大型AI供應商的依賴。",
        "why": "30億歐元融資及約210億歐元估值直接改變歐洲AI競爭格局，亦為Mistral擴大模型訓練、算力和商業部署提供資本。",
        "watchNext": "留意Mistral如何配置新資金、擴建運算基建，以及其年度經常性收入能否按計劃達標。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/world/europe/french-ai-company-mistral-hits-24-billion-valuation-funding-round-2026-09-08/",
        "timeLabel": "9月8日13:02 HKT報道",
        "publishedAt": "2026-09-08T13:02:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/world/europe/french-ai-company-mistral-hits-24-billion-valuation-funding-round-2026-09-08/"}],
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
        "id": "football-mctominay-heart-procedure-20260908",
        "desk": "football",
        "deskSlugs": ["football"],
        "section": "Football｜意大利／歐聯",
        "status": "LATEST",
        "title": "麥湯文尼完成心律問題消融手術　預計約兩周後復操",
        "dek": "拿玻里確認Scott McTominay接受治療輕微良性心律不整的消融手術並順利完成；他將缺席對阿仙奴的歐聯賽事及兩場意甲。",
        "summary": "拿玻里中場Scott McTominay完成心臟消融手術，預計休息約兩周後恢復訓練，期間將缺席歐聯及意甲賽事。",
        "body": "路透社9月8日報道，拿玻里中場Scott McTominay在曼徹斯特的Spire Manchester Hospital完成原定的心臟消融手術，以處理上周確診的輕微良性心律不整。拿玻里表示手術順利完成，他會休息約兩周後再恢復訓練。\n\n29歲的蘇格蘭國腳因此將缺席周三對阿仙奴的歐聯揭幕戰，以及意甲對博洛尼亞和費倫天拿的賽事。球會預計他在其後的國際賽期恢復全面訓練。",
        "context": "球員健康狀況已直接影響拿玻里的歐聯及聯賽排陣，並涉及明確的復操時間表。",
        "why": "這是當日已確認的足球球員健康、傷停及賽程影響新聞，應只歸Football版，不回流World、Asia或Finance。",
        "watchNext": "留意麥湯文尼康復進度、拿玻里對阿仙奴的中場安排，以及他能否按計劃在約兩周後復操。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/sports/soccer/napolis-mctominay-miss-arsenal-clash-after-successful-heart-procedure-2026-09-08/",
        "timeLabel": "9月8日20:12 HKT報道",
        "publishedAt": "2026-09-08T20:12:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/napolis-mctominay-miss-arsenal-clash-after-successful-heart-procedure-2026-09-08/"}],
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
