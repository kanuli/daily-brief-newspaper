#!/usr/bin/env python3
"""Editor-in-Chief freshness recovery for verified topic-desk events.

Freshness recovery is fail-closed. It first reuses current verified Daily copy
for the correct hard-routed desk. A small recovery template is permitted only
when it is independently current and source-backed; stale templates are never
retimestamped or used to manufacture freshness.
"""
from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

from desk_freshness_policy import PUBLIC_DESK_FRESHNESS_HOURS, editorial_story_time, routed_slugs

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DESK_PATH = DATA / "desk-latest.json"
LATEST_PATH = DATA / "latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))

RECOVERY = {
    "world": {
        "id": "world-iran-us-tanker-attacks-hormuz-20260909", "desk": "world", "deskSlugs": ["world"], "section": "國際｜中東", "status": "LATEST",
        "title": "伊朗與美國擴大海上互擊　霍爾木茲海峽航運風險急升",
        "dek": "伊朗與美國9月9日擴大針對海上目標的報復行動，多艘油輪及商船受波及，霍爾木茲海峽能源運輸再受衝擊。",
        "summary": "路透社9月9日報道，伊朗與美國展開這場衝突以來最大規模的海上互擊；伊朗稱襲擊海峽附近多艘船隻，美方則打擊伊朗油輪，區內航運與能源供應風險同步上升。",
        "body": "伊朗與美國9月9日把持續數月的軍事對抗進一步延伸至海上航運。路透社報道，伊朗在霍爾木茲海峽附近攻擊多艘船隻，稱是回應美方摧毀伊朗油輪；美方則表示其行動與伊朗對美軍及海上力量的威脅有關。\n\n霍爾木茲海峽是全球重要能源運輸通道，今次互擊令商船、油輪及液化天然氣運輸面對更高安全風險，油價亦隨局勢升級而上升。",
        "context": "美伊衝突持續升級之際，海上航線已成為新的直接交鋒場域，並牽動全球能源運輸與區內安全。",
        "why": "霍爾木茲海峽承載全球大量石油運輸，任何持續攻擊都可能迅速擴大至航運、能源價格及區域安全層面。",
        "watchNext": "留意美伊是否再擴大海上打擊、主要航運公司是否改道，以及區內國家與國際斡旋方能否降低衝突強度。",
        "sourceName": "Reuters", "sourceUrl": "https://www.reuters.com/world/middle-east/iran-attacks-us-base-jordan-ships-near-hormuz-after-tankers-sunk-2026-09-09/", "timeLabel": "9月9日21:10 HKT核實", "verifiedAt": "2026-09-09T21:10:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/world/middle-east/iran-attacks-us-base-jordan-ships-near-hormuz-after-tankers-sunk-2026-09-09/"}]
    },
    "hong-kong": {
        "id": "hong-kong-tung-chee-hwa-government-tributes-20260909", "desk": "hong-kong", "deskSlugs": ["hong-kong"], "section": "香港｜政情", "status": "LATEST",
        "title": "董建華逝世終年89歲　特首李家超代表特區致哀",
        "dek": "香港首任行政長官董建華逝世，終年89歲；李家超表示深切哀悼，並代表香港特區向其家人致以慰問。",
        "summary": "香港特區政府9月9日公布，首任行政長官、全國政協前副主席董建華逝世，終年89歲；行政長官李家超發表聲明，回顧其任內應對亞洲金融風暴、推動香港與內地經貿聯繫等工作。",
        "body": "香港首任行政長官董建華逝世，終年89歲。行政長官李家超9月9日發表聲明表示深切哀悼，並代表香港特別行政區向董建華家人致以慰問。董建華於1997年出任香港特區首任行政長官，至2005年3月離任，其後擔任第十至第十三屆全國政協副主席。\n\n李家超在聲明中提到，董建華任內經歷亞洲金融風暴等重大挑戰，並推動香港與內地的經貿聯繫及協同發展。",
        "context": "董建華是香港回歸後首任行政長官，任期由1997年至2005年，之後繼續在全國政協任職多年。",
        "why": "首任行政長官逝世及特區政府正式悼念，涉及香港重要政治人物及特區成立初期的公共歷史，具有即時本地新聞價值。",
        "watchNext": "留意特區政府及家屬公布的悼念、治喪安排，以及香港各界後續回應。",
        "sourceName": "香港特別行政區政府新聞公報 / Reuters", "sourceUrl": "https://www.info.gov.hk/gia/general/202609/09/P2026090900069.htm", "timeLabel": "9月9日21:19 HKT核實", "verifiedAt": "2026-09-09T21:19:00+08:00",
        "sources": [{"name": "香港特別行政區政府新聞公報", "url": "https://www.info.gov.hk/gia/general/202609/09/P2026090900069.htm"}, {"name": "Reuters", "url": "https://www.reuters.com/world/china/tung-chee-hwa-hong-kongs-first-leader-under-chinese-rule-dies-89-2026-09-08/"}]
    },
    "manchester-united": {
        "id": "manchester-united-sabah-champions-league-preview-20260909", "desk": "manchester-united", "deskSlugs": ["manchester-united", "football"], "section": "Manchester United｜歐聯", "status": "LATEST",
        "title": "曼聯迎戰Sabah前更新歐聯賽前指南　奧脫福特準備下一場歐洲賽",
        "dek": "曼聯官網把對Sabah列為下一場正式賽事，並發布收看及跟進指南；球隊在2比2賽和愛華頓後轉入歐聯備戰。",
        "summary": "曼聯官方網站最新賽程確認，球隊下一場正式賽事是在奧脫福特迎戰Sabah的歐聯比賽；官網同時保留最新賽前指南及球迷收看資訊。",
        "body": "曼聯官方網站9月9日仍把主場對Sabah列為下一場正式賽事，並刊出『How to watch and follow: United v Sabah』賽前指南。官網賽程顯示，球隊在9月6日作客2比2賽和愛華頓後，下一站是奧脫福特的歐聯比賽。\n\n這項更新直接關乎曼聯下一場正式賽事、球迷收看安排及比賽日準備。",
        "context": "曼聯在英超開季後轉入歐聯賽程，對Sabah一戰是球隊近期重要主場歐洲賽。", "why": "球會官方仍把Sabah列為下一場正式賽事，屬當前而可核實的曼聯賽前資訊。", "watchNext": "留意曼聯公布比賽日大軍、傷兵更新、正選陣容及賽前記者會內容。",
        "sourceName": "Manchester United", "sourceUrl": "https://www.manutd.com/en", "timeLabel": "9月9日08:27 HKT核實", "verifiedAt": "2026-09-09T08:27:00+08:00",
        "sources": [{"name": "Manchester United", "url": "https://www.manutd.com/en"}, {"name": "Manchester United Matches", "url": "https://www.manutd.com/en/mutv/matches/mens-team"}]
    },
    "football": {
        "id": "football-belgium-courtois-nations-league-20260909", "desk": "football", "deskSlugs": ["football"], "section": "足球｜比利時", "status": "LATEST",
        "title": "古圖奧斯獲准缺席比利時歐國聯賽程　未退出國家隊", "dek": "比利時門將古圖奧斯獲准避戰未來數月的歐國聯賽事，但強調仍會代表國家隊，並計劃參與明年歐洲國家盃外圍賽。",
        "summary": "路透社9月9日報道，古圖奧斯獲比利時隊批准缺席即將展開的歐國聯賽程；他表示決定主要與賽程及身體負荷有關，並非退出國家隊。",
        "body": "比利時門將古圖奧斯將不參與球隊未來數月的歐國聯賽程。路透社引述比利時媒體報道，國家隊已批准這名34歲門將暫時避戰；古圖奧斯同時表明自己沒有退出國際賽，仍計劃在明年3月開始的歐洲國家盃外圍賽重新為國家隊候命。\n\n比利時在今屆歐國聯將與法國、意大利及土耳其交手，三個月內共有六場比賽。古圖奧斯表示，高密度球會與國際賽賽程令身體負荷增加，因此選擇在今輪賽事休息；新任主帥雲邦美據報亦支持這項安排。",
        "context": "古圖奧斯仍是比利時重要門將，他今次缺席屬賽程管理決定，而非國際賽退役。", "why": "門將人選及主力球員可用性直接影響比利時接下來六場歐國聯比賽的部署，亦涉及球會與國家隊之間的工作量管理。", "watchNext": "留意比利時公布歐國聯正式名單、門將排序，以及古圖奧斯在明年歐洲國家盃外圍賽前是否恢復入選。",
        "sourceName": "Reuters", "sourceUrl": "https://www.reuters.com/sports/soccer/courtois-given-green-light-skip-belgiums-nations-league-campaign-reports-say-2026-09-09/", "timeLabel": "9月9日18:12 HKT核實", "verifiedAt": "2026-09-09T18:12:00+08:00",
        "sources": [{"name": "Reuters", "url": "https://www.reuters.com/sports/soccer/courtois-given-green-light-skip-belgiums-nations-league-campaign-reports-say-2026-09-09/"}]
    }
}


def newest_age_hours(stories, now):
    stamps=[]
    for story in stories:
        if isinstance(story,dict):
            stamp=editorial_story_time(story,now=now.astimezone(dt.timezone.utc))
            if stamp is not None: stamps.append(stamp.astimezone(HKT))
    if not stamps: return float("inf")
    return max(0.0,(now-max(stamps)).total_seconds()/3600.0)


def _insert(desks,slug,story):
    story=copy.deepcopy(story); story["status"]="LATEST"; routes=routed_slugs(story)
    if slug not in routes: raise SystemExit(f"DESK_FRESHNESS_RECOVERY_MISROUTE slug={slug} routes={routes}")
    sid=str(story.get("id") or ""); current=desks.setdefault(slug,[])
    current[:]=[x for x in current if str(x.get("id") or "") != sid]; current.insert(0,story)
    for route in routes:
        if route==slug: continue
        routed=desks.setdefault(route,[]); routed[:]=[x for x in routed if str(x.get("id") or "") != sid]; routed.insert(0,copy.deepcopy(story))
        print(f"DESK_FRESHNESS_RECOVERY_CROSS_ROUTE id={sid} route={route}")


def _refresh_recovery_copy(desks):
    changed=False; by_id={str(story["id"]):story for story in RECOVERY.values()}
    for slug,stories in desks.items():
        if not isinstance(stories,list): continue
        for idx,story in enumerate(stories):
            if not isinstance(story,dict): continue
            template=by_id.get(str(story.get("id") or ""))
            if not template: continue
            replacement=copy.deepcopy(template); replacement["status"]=story.get("status") or replacement.get("status") or "LATEST"
            if story != replacement:
                stories[idx]=replacement; changed=True; print(f"DESK_FRESHNESS_RECOVERY_COPY_REFRESH id={replacement['id']} desk={slug}")
    return changed


def main():
    data=json.loads(DESK_PATH.read_text(encoding="utf-8")); latest=json.loads(LATEST_PATH.read_text(encoding="utf-8")); desks=data.setdefault("desks",{}); now=dt.datetime.now(HKT)
    changed=_refresh_recovery_copy(desks); daily=[x for x in (latest.get("articles") or []) if isinstance(x,dict)]
    for slug,sla in PUBLIC_DESK_FRESHNESS_HOURS.items():
        current=desks.setdefault(slug,[]); age=newest_age_hours(current,now)
        if age <= sla:
            print(f"DESK_FRESHNESS_RECOVERY_SKIP slug={slug} age_h={age:.2f} sla_h={sla}"); continue
        candidates=[]
        for story in daily:
            if slug not in routed_slugs(story): continue
            story_age=newest_age_hours([story],now)
            if story_age <= sla: candidates.append((story_age,story))
        if candidates:
            candidates.sort(key=lambda pair:pair[0]); _insert(desks,slug,candidates[0][1]); changed=True; print(f"DESK_FRESHNESS_RECOVERY_DAILY slug={slug} id={candidates[0][1].get('id')}"); continue
        template=RECOVERY.get(slug)
        if not template: raise SystemExit(f"DESK_FRESHNESS_RECOVERY_NO_CURRENT_SOURCE slug={slug} age_h={age:.2f} sla_h={sla}; refusing false repair")
        template_age=newest_age_hours([template],now)
        if template_age > sla: raise SystemExit(f"DESK_FRESHNESS_RECOVERY_TEMPLATE_STALE slug={slug} template_age_h={template_age:.2f} sla_h={sla}; refusing false repair")
        _insert(desks,slug,template); changed=True; print(f"DESK_FRESHNESS_RECOVERY_ADD slug={slug} age_h={age:.2f} id={template['id']}")
    if changed:
        DESK_PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print("DESK_FRESHNESS_RECOVERY_APPLIED")
    else: print("DESK_FRESHNESS_RECOVERY_NOOP")


if __name__ == "__main__": main()
