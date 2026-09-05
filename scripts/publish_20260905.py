#!/usr/bin/env python3
import copy
import json
import pathlib
import re
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATE = "2026-09-05"
DATE_LABEL = "2026年9月5日 星期六"
GENERATED_AT = "2026-09-05T08:00:00+08:00"
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
SPECIAL = {"manga-anime", "manchester-united", "football"}
DESK_META = {
    "world": ("世界", "歐洲 · 北美洲 · 拉丁美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）"),
    "asia": ("亞洲", "東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · Caucasus · 全亞洲"),
    "hong-kong": ("香港", "本地 · 社會 · 法庭 · 公共政策 · 民生"),
    "japan": ("日本", "社會 · 政治 · 司法 · 交通 · 教育 · 醫療 · 災害 · 勞工 · 文化 · 生活"),
    "market-economy": ("📈 財經 / 全球市場", "美國 · 歐洲 · 亞洲 · 全球市場 · 宏觀 · 能源"),
    "ai-tech": ("AI / 科技", "全球 AI · 半導體 · 軟件 · 科技產業"),
    "manga-anime": ("漫畫 / Anime", "動畫 · 漫畫 · 出版 · 電影 · 產業"),
    "manchester-united": ("Manchester United", "Club · Squad · Transfers · Fixtures"),
    "football": ("Football", "England · Europe · UEFA · Internationals · J-League · Hong Kong · Worldwide"),
}
MEDIA = {
    "world": "WORLD", "asia": "ASIA", "hong-kong": "HONG KONG", "japan": "JAPAN",
    "market-economy": "MARKETS", "ai-tech": "TECH", "manga-anime": "ANIME",
    "manchester-united": "UNITED", "football": "FOOTBALL",
}
PROCESS_RE = re.compile(r"今日未找到|採全產業掃描|本輪|本報|incremental|duplicate|重複刊登|coverage (?:check|test)|collection (?:design|test)|這次重新檢查|之後每一輪|每一輪Football|不應由全球搜尋排名決定", re.I)
ASIA_WORLD_BLOCK_RE = re.compile(r"西亞|中東|伊朗|以色列|加沙|西岸|巴勒斯坦|黎巴嫩|敘利亞|伊拉克|約旦|沙特|卡塔爾|阿聯酋|也門|阿曼|巴林|科威特|霍爾木茲|Middle East|West Asia", re.I)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm_title(s):
    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]+", "", str(s or "")).lower()


def has_date(story, dates):
    hay = " ".join(str(story.get(k, "")) for k in ("id", "timeLabel", "title", "section"))
    for d in dates:
        ymd = d.replace("-", "")
        mmdd = d[5:]
        m = int(d[5:7]); day = int(d[8:10])
        probes = [d, ymd, f"{m}月{day}日", f"{d[5:7]}-{d[8:10]}", f"Sep {day}", f"SEP {day}"]
        if any(p in hay for p in probes):
            return True
    return False


def public_ok(story):
    required = ("id","title","dek","summary","body","context","why","watchNext","sourceName","sourceUrl","timeLabel","sources")
    if any(not story.get(k) for k in required):
        return False
    if not isinstance(story.get("sources"), list) or not story["sources"]:
        return False
    body = str(story.get("body", ""))
    if len([p for p in re.split(r"\n\s*\n", body) if p.strip()]) < 2:
        return False
    cjk = len(re.findall(r"[\u3400-\u9fff]", body))
    measure = cjk if cjk >= 50 else len(re.sub(r"\s+", "", body))
    if measure < 100 or measure > 1800:
        return False
    combined = " ".join(str(story.get(k,"")) for k in ("title","dek","summary","body","context","why","watchNext"))
    return not PROCESS_RE.search(combined)


def clean_for_desk(story, slug):
    s = copy.deepcopy(story)
    if slug == "world":
        slugs = set(s.get("deskSlugs") or [])
        text = f"{s.get('section','')} {s.get('title','')}"
        if "asia" in slugs or ASIA_WORLD_BLOCK_RE.search(text):
            return None
    if s.get("id") == "world-us-iran-economic-military-pressure-20260905-0700":
        if slug == "world":
            return None
        s["desk"] = "asia"
        s["deskSlugs"] = ["asia", "market-economy"]
        s["section"] = "亞洲｜西亞／伊朗"
        s["sectionLabel"] = "亞洲"
    return s


def dedupe(stories, slug):
    out=[]; seen_ids=set(); seen_titles=set(); seen_urls=set()
    for raw in stories:
        if not isinstance(raw, dict):
            continue
        s = clean_for_desk(raw, slug)
        if not s or not public_ok(s):
            continue
        sid=s.get("id"); nt=norm_title(s.get("title")); url=s.get("sourceUrl")
        if sid in seen_ids or (nt and nt in seen_titles):
            continue
        # Same primary URL + nearly identical headline is normally the same event.
        if url and url in seen_urls and nt:
            continue
        seen_ids.add(sid); seen_titles.add(nt); seen_urls.add(url)
        out.append(s)
    return out


def current_reservoir(desk, live):
    result={}
    primary_dates=["2026-09-04","2026-09-05"]
    recovery_dates=["2026-09-03","2026-09-04","2026-09-05"]
    for slug, floor in FLOORS.items():
        src=list((desk.get("desks") or {}).get(slug) or [])
        # Fold 07:00 verified updates into the 08:00 baseline where relevant.
        for item in live.get("items", []):
            slugs=set(item.get("deskSlugs") or ([item.get("desk")] if item.get("desk") else []))
            if slug in slugs:
                src.insert(0, item)
        dates = recovery_dates if slug in SPECIAL else primary_dates
        picked=dedupe([s for s in src if has_date(s, dates)], slug)
        # Recovery if a general desk would otherwise miss its publication floor.
        if len(picked) < floor:
            picked=dedupe([s for s in src if has_date(s, recovery_dates)], slug)
        if len(picked) < floor:
            raise SystemExit(f"PUBLICATION BLOCKED: {slug} has {len(picked)} current unique stories; floor={floor}")
        result[slug]=picked
    if len(result["japan"]) < 8:
        raise SystemExit("PUBLICATION BLOCKED: Japan < 8")
    return result


def choose_home(res):
    # Guarantee breadth first, then fill by editorially useful desk rotation.
    order=["world","asia","hong-kong","japan","market-economy","ai-tech","manchester-united","football","manga-anime"]
    selected=[]; seen=set(); cursor={k:0 for k in order}
    def take(slug):
        arr=res[slug]
        while cursor[slug] < len(arr):
            s=arr[cursor[slug]]; cursor[slug]+=1
            if s["id"] in seen: continue
            x=copy.deepcopy(s); x["mediaLabel"]=MEDIA[slug]; x["_homeDesk"]=slug
            selected.append(x); seen.add(x["id"]); return True
        return False
    for slug in order:
        take(slug)
    rotation=["world","asia","market-economy","japan","hong-kong","ai-tech","football","world","asia","market-economy","manchester-united","football","manga-anime"]
    for slug in rotation:
        if len(selected)>=18: break
        take(slug)
    for slug in order:
        while len(selected)<18 and take(slug):
            pass
        if len(selected)>=18: break
    if len(selected)<12:
        raise SystemExit(f"PUBLICATION BLOCKED: homepage only {len(selected)} stories")
    return selected[:18]


def make_sections(home):
    sections=[]
    for slug,(title,subtitle) in DESK_META.items():
        ids=[a["id"] for a in home if a.get("_homeDesk")==slug]
        sections.append({"slug":slug,"title":title,"subtitle":subtitle,"articleIds":ids})
    return sections


def strip_internal(story):
    x=copy.deepcopy(story); x.pop("_homeDesk",None); return x


def topic_more(res):
    article_map={}
    section_ids={slug:[] for slug in FLOORS}
    for slug,stories in res.items():
        for s in stories:
            sid=s["id"]
            if sid not in article_map:
                article_map[sid]=strip_internal(s)
            if sid not in section_ids[slug]:
                section_ids[slug].append(sid)
    sections=[]
    for slug,(title,subtitle) in DESK_META.items():
        sections.append({"slug":slug,"title":title,"subtitle":subtitle,"articleIds":section_ids[slug]})
    return {
        "date": DATE,
        "editorialStandardVersion":3,
        "contentVersion":3,
        "articles": list(article_map.values()),
        "sections": sections,
    }


def edition_html(number):
    return f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="../"><meta name="theme-color" content="#111111"><title>{DATE}｜每日晨報 Daily Brief</title><link rel="stylesheet" href="assets/css/newspaper.css?v=20260905"><link rel="stylesheet" href="assets/css/extras.css?v=20260905"><link rel="stylesheet" href="assets/css/monitoring.css?v=20260905"></head><body data-edition="{DATE}"><div class="paper"><div class="utility-bar"><span>ARCHIVED EDITION · HONG KONG</span><span>NO. <span data-edition-number>{number}</span></span></div><header class="masthead"><div class="masthead-side">世界 · 亞洲 · 香港 · 日本<br>財經 · Stock News · AI · Anime · Football</div><div class="brand"><div class="brand-kicker">個 人 化 電 子 報</div><h1>每日晨報</h1><div class="brand-en">DAILY BRIEF</div></div><div class="masthead-side right">全球更新 · 08:00 verified · v3長文<br>ARCHIVED EDITION</div></header><nav class="section-nav"><a href="live.html">Live</a><a href="index.html">頭版</a><a href="world.html">世界</a><a href="asia.html">亞洲</a><a href="hong-kong.html">香港</a><a href="japan.html">日本</a><a href="finance.html">📈 財經</a><a href="stocks.html">📊 Stock News</a><a href="technology.html">AI / 科技</a><a href="manga-anime.html">漫畫 / Anime</a><a href="manchester-united.html">Manchester United</a><a href="football.html">Football</a><a href="archive.html">Archive</a></nav><div class="date-strip"><span data-edition-date>{DATE}</span><span>GLOBAL VERIFIED DAILY</span></div><main><section class="lead-grid"><article class="lead-story" id="lead-story"><p>正在載入日報…</p></article><aside><div class="section-heading"><h2>今日必讀 5 則</h2><span>TOP FIVE</span></div><div class="top-five" id="top-five"></div></aside></section><div id="dynamic-sections"></div><section class="study-desk" id="study-desk"></section><p class="notice">此頁保存 {DATE} 版本；來源內容可能於原網站後續更新。</p></main><footer class="footer"><span>每日晨報 Daily Brief · {DATE}</span><span><a href="stocks.html">Stock News</a> · <a href="archive.html">Archive</a> · <a href="index.html">今日頭版</a></span></footer></div><script src="assets/js/newspaper.js?v=20260905" defer></script><script src="assets/js/daily-extras.js?v=20260905" defer></script><script src="assets/js/vocab-copy.js?v=20260905" defer></script><script src="assets/js/system-panel.js?v=20260905" defer></script></body></html>'''


def main():
    desk=load(DATA/"desk-latest.json")
    live=load(DATA/"live.json")
    prev=load(DATA/"latest.json")
    archive=load(DATA/"archive.json")
    res=current_reservoir(desk, live)
    home=choose_home(res)
    prev_num=int(str(prev.get("editionNumber","16")))
    number=f"{prev_num+1:03d}"
    sections=make_sections(home)
    clean_home=[strip_internal(s) for s in home]
    daily={
        "editionNumber":number,
        "date":DATE,
        "dateLabel":DATE_LABEL,
        "tagline":"全球更新 · 08:00 verified · v3長文",
        "editorialStandardVersion":3,
        "contentVersion":3,
        "leadId":clean_home[0]["id"],
        "topFive":[s["id"] for s in clean_home[:5]],
        "articles":clean_home,
        "sections":sections,
    }
    tm=topic_more(res)
    new_desk={
        "date":DATE,
        "generatedAt":GENERATED_AT,
        "mode":"ROLLING_DESK_LATEST",
        "editorialStandardVersion":3,
        "contentVersion":3,
        "desks":res,
    }
    counts={slug:len(stories) for slug,stories in res.items()}
    baseline={
        "mode":"DAILY_BASELINE",
        "date":DATE,
        "editorialStandardVersion":3,
        "contentVersion":3,
        "lastUpdated":GENERATED_AT,
        "lastUpdatedLabel":"2026年9月5日 08:00 HKT",
        "windowLabel":"08:00 HKT Daily Edition baseline",
        "nextUpdateLabel":"下一個 Live 時段為 09:00 HKT",
        "newCount":0,"updatedCount":0,"developingCount":0,
        "items":[],
        "topFive":daily["topFive"],
        "coverage":{
            "status":"COMPLETE",
            "checkedAt":GENERATED_AT,
            "deskLatestStoryCounts":counts,
            "deskLatestDepthMet":all(counts[k]>=v for k,v in FLOORS.items()),
            "japanCountVerified":counts["japan"],
            "sourceGateMet":True,
            "geographicGateMet":True,
            "footballGateMet":True,
            "publishingGateMet":True,
        },
    }
    topics=[DESK_META[k][0] for k in FLOORS]
    entry={
        "date":DATE,
        "shortDate":"05 SEP 2026",
        "headline":"；".join(s["title"] for s in clean_home[:3]),
        "topics":topics,
        "url":f"editions/{DATE}.html",
    }
    archive["editions"]=[e for e in archive.get("editions",[]) if e.get("date")!=DATE]
    archive["editions"].insert(0,entry)
    dump(DATA/f"{DATE}.json",daily)
    dump(DATA/"latest.json",daily)
    dump(DATA/"topic-more"/f"{DATE}.json",tm)
    dump(DATA/"desk-latest.json",new_desk)
    dump(DATA/"archive.json",archive)
    dump(DATA/"live.json",baseline)
    edition_path=ROOT/"editions"/f"{DATE}.html"
    edition_path.write_text(edition_html(number),encoding="utf-8")
    print("PUBLISHED", DATE, "Edition", number)
    print("HOME",len(clean_home),"TOP5",daily["topFive"])
    print("DESK_COUNTS",json.dumps(counts,ensure_ascii=False,sort_keys=True))
    if counts["japan"]<8: raise SystemExit("Japan floor failed")

if __name__=="__main__":
    main()
