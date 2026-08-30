#!/usr/bin/env python3
import copy
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATE = "2026-08-30"
DATE_LABEL = "2026年8月30日 星期日"
EDITION = "011"
STAMP = "2026-08-30T08:00:00+08:00"

DESKS = [
    ("world", "世界", "歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）"),
    ("asia", "亞洲", "東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · Caucasus · 全亞洲"),
    ("hong-kong", "香港", "本地 · 社會 · 法庭 · 公共政策 · 民生"),
    ("japan", "日本", "社會 · 政治 · 司法／犯罪 · 交通 · 教育 · 醫療 · 災害／天氣 · 勞工／人口 · 文化／生活"),
    ("market-economy", "📈 財經 / 全球市場", "美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球市場"),
    ("ai-tech", "AI / 科技", "全球 AI · 半導體 · 雲端 · 軟件 · 網絡安全 · 科技監管"),
    ("manga-anime", "漫畫 / Anime", "動畫 · 漫畫 · 出版 · 票房 · 聲優 · 平台 · 產業"),
    ("manchester-united", "Manchester United", "Club · Squad · Injuries · Fixtures · Transfers"),
    ("football", "Football", "England · Europe · UEFA · International · J-League · Hong Kong · Worldwide"),
]
MINIMUMS = {"world":8,"asia":8,"hong-kong":6,"japan":8,"market-economy":8,"ai-tech":6,"manga-anime":4,"manchester-united":4,"football":10}
HOMEPAGE_QUOTA = {"world":3,"asia":3,"hong-kong":2,"japan":2,"market-economy":2,"ai-tech":1,"manga-anime":1,"manchester-united":1,"football":1}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def clean_story(story, primary_slug):
    s = copy.deepcopy(story)
    s["desk"] = primary_slug
    s["status"] = "LATEST"
    s.setdefault("deskSlugs", [primary_slug])
    if primary_slug not in s["deskSlugs"]:
        s["deskSlugs"].append(primary_slug)
    s.setdefault("mediaLabel", dict((slug,title) for slug,title,_ in DESKS).get(primary_slug, primary_slug))
    s.setdefault("sectionLabel", dict((slug,title) for slug,title,_ in DESKS).get(primary_slug, primary_slug))
    s.setdefault("image", None)
    return s


def norm_event(story):
    # ID is the primary dedupe key. This secondary key catches common rewritten copies.
    title = ''.join(ch.lower() for ch in str(story.get('title','')) if ch.isalnum())
    return title[:48]


def main():
    desk_path = DATA / "desk-latest.json"
    desk = load(desk_path)
    if desk.get("contentVersion") != 3 or desk.get("editorialStandardVersion") != 3:
        raise SystemExit("desk-latest is not v3")
    desks = desk.get("desks", {})
    counts = {slug: len(desks.get(slug, [])) for slug,_,_ in DESKS}
    failures = {slug:(counts.get(slug,0), minimum) for slug,minimum in MINIMUMS.items() if counts.get(slug,0) < minimum}
    if failures:
        raise SystemExit(f"Hard desk floors not met before Daily build: {failures}")
    if counts["japan"] < 8:
        raise SystemExit(f"Japan publication failure: {counts['japan']} < 8")

    selected = []
    selected_ids = set()
    selected_events = set()
    primary_for_id = {}
    for slug,_,_ in DESKS:
        taken = 0
        for story in desks.get(slug, []):
            sid = story.get("id")
            event = norm_event(story)
            if not sid or sid in selected_ids or (event and event in selected_events):
                continue
            selected.append(clean_story(story, slug))
            selected_ids.add(sid)
            if event: selected_events.add(event)
            primary_for_id[sid] = slug
            taken += 1
            if taken >= HOMEPAGE_QUOTA[slug]:
                break

    # Keep the homepage in the requested 12–20 range even if cross-desk duplicates reduced quota picks.
    if len(selected) < 16:
        for slug,_,_ in DESKS:
            for story in desks.get(slug, []):
                sid = story.get("id")
                event = norm_event(story)
                if not sid or sid in selected_ids or (event and event in selected_events):
                    continue
                selected.append(clean_story(story, slug))
                selected_ids.add(sid)
                if event: selected_events.add(event)
                primary_for_id[sid] = slug
                if len(selected) >= 16:
                    break
            if len(selected) >= 16:
                break
    selected = selected[:20]

    # Top Five = five cross-desk highest-ranked stories, not a site-wide cap.
    top_priority = ["world","asia","market-economy","japan","football","hong-kong","ai-tech","manchester-united","manga-anime"]
    top = []
    for slug in top_priority:
        hit = next((s["id"] for s in selected if primary_for_id.get(s["id"]) == slug and s["id"] not in top), None)
        if hit: top.append(hit)
        if len(top) == 5: break
    if len(top) < 5:
        top.extend([s["id"] for s in selected if s["id"] not in top][:5-len(top)])

    sections = []
    for slug,title,subtitle in DESKS:
        ids = [s["id"] for s in selected if primary_for_id.get(s["id"]) == slug]
        sections.append({"slug":slug,"title":title,"subtitle":subtitle,"articleIds":ids})

    latest = {
        "editionNumber": EDITION,
        "date": DATE,
        "dateLabel": DATE_LABEL,
        "tagline": "全球更新 · 08:00 verified · v3長文",
        "editorialStandardVersion": 3,
        "contentVersion": 3,
        "leadId": top[0],
        "topFive": top,
        "articles": selected,
        "sections": sections,
    }
    write(DATA / "latest.json", latest)
    write(DATA / f"{DATE}.json", latest)

    # Topic More is deliberately broader than the homepage. Keep every distinct current story not already on the homepage.
    extras = []
    extra_ids = set()
    extra_events = set()
    extra_primary = {}
    for slug,_,_ in DESKS:
        for story in desks.get(slug, []):
            sid = story.get("id")
            event = norm_event(story)
            if not sid or sid in selected_ids or sid in extra_ids or (event and event in extra_events):
                continue
            extras.append(clean_story(story, slug))
            extra_ids.add(sid)
            if event: extra_events.add(event)
            extra_primary[sid] = slug
    topic_sections = []
    for slug,title,subtitle in DESKS:
        ids = [s["id"] for s in extras if extra_primary.get(s["id"]) == slug]
        topic_sections.append({"slug":slug,"title":title,"subtitle":subtitle,"articleIds":ids})
    topic_more = {
        "date": DATE,
        "editorialStandardVersion": 3,
        "contentVersion": 3,
        "articles": extras,
        "sections": topic_sections,
    }
    write(DATA / "topic-more" / f"{DATE}.json", topic_more)

    # 08:00 baseline: retain the entire verified reservoir, only stamp it as today's Daily baseline.
    desk["date"] = DATE
    desk["generatedAt"] = STAMP
    desk["mode"] = "ROLLING_DESK_LATEST"
    desk["editorialStandardVersion"] = 3
    desk["contentVersion"] = 3
    write(desk_path, desk)

    # 08:00 is Daily-only: no incremental Live stories are published at this slot.
    live = {
        "mode": "DAILY_BASELINE",
        "date": DATE,
        "editorialStandardVersion": 3,
        "contentVersion": 3,
        "lastUpdated": STAMP,
        "lastUpdatedLabel": "2026年8月30日 08:00 HKT",
        "nextUpdateLabel": "下一輪預定 09:00 HKT",
        "windowLabel": "08:00 Daily Edition baseline",
        "newCount": 0,
        "updatedCount": 0,
        "developingCount": 0,
        "coverage": {
            "status": "DAILY_BASELINE",
            "checkedAt": STAMP,
            "deskLatestStoryCounts": counts,
            "deskLatestDepthMet": True,
            "qaNote": "08:00 Daily publication baseline; incremental Live resumes at 09:00 HKT."
        },
        "items": []
    }
    write(DATA / "live.json", live)

    archive_path = DATA / "archive.json"
    archive = load(archive_path)
    editions = archive.setdefault("editions", [])
    editions[:] = [e for e in editions if e.get("date") != DATE]
    top_titles = [next(s["title"] for s in selected if s["id"] == sid) for sid in top[:3]]
    editions.insert(0, {
        "date": DATE,
        "shortDate": "30 AUG 2026",
        "headline": "；".join(top_titles),
        "topics": [title for _,title,_ in DESKS],
        "url": f"editions/{DATE}.html"
    })
    write(archive_path, archive)

    html = f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="../"><meta name="theme-color" content="#111111"><title>{DATE}｜每日晨報 Daily Brief</title><link rel="stylesheet" href="assets/css/newspaper.css?v=20260830"><link rel="stylesheet" href="assets/css/extras.css?v=20260830"><link rel="stylesheet" href="assets/css/monitoring.css?v=20260830"></head><body data-edition="{DATE}"><div class="paper"><div class="utility-bar"><span>ARCHIVED EDITION · HONG KONG</span><span>NO. <span data-edition-number>{EDITION}</span></span></div><header class="masthead"><div class="masthead-side">世界 · 亞洲 · 香港 · 日本<br>財經 · Stock News · AI · Anime · Football</div><div class="brand"><div class="brand-kicker">個 人 化 電 子 報</div><h1>每日晨報</h1><div class="brand-en">DAILY BRIEF</div></div><div class="masthead-side right"><span data-edition-tagline>全球更新 · 08:00 verified · v3長文</span><br>ARCHIVED EDITION</div></header><nav class="section-nav" aria-label="新聞分版"><a href="live.html">Live</a><a href="index.html">頭版</a><a href="world.html">世界</a><a href="asia.html">亞洲</a><a href="hong-kong.html">香港</a><a href="japan.html">日本</a><a href="finance.html">📈 財經</a><a href="stocks.html">📊 Stock News</a><a href="technology.html">AI / 科技</a><a href="manga-anime.html">漫畫 / Anime</a><a href="manchester-united.html">Manchester United</a><a href="football.html">Football</a><a href="archive.html">Archive</a></nav><div class="date-strip"><span data-edition-date>{DATE}</span><span>GLOBAL VERIFIED DAILY</span></div><main><section class="lead-grid"><article class="lead-story" id="lead-story"><p>正在載入日報…</p></article><aside><div class="section-heading"><h2>今日必讀 5 則</h2><span>TOP FIVE</span></div><div class="top-five" id="top-five"></div></aside></section><div id="dynamic-sections"></div><section class="study-desk" id="study-desk"></section><p class="notice">此頁保存 {DATE} 版本；來源內容可能於原網站後續更新。</p></main><footer class="footer"><span>每日晨報 Daily Brief · {DATE}</span><span><a href="stocks.html">Stock News</a> · <a href="archive.html">Archive</a> · <a href="index.html">今日頭版</a></span></footer></div><script src="assets/js/newspaper.js?v=20260830" defer></script><script src="assets/js/daily-extras.js?v=20260830" defer></script><script src="assets/js/vocab-copy.js?v=20260830" defer></script><script src="assets/js/system-panel.js?v=20260830" defer></script></body></html>'''
    edition_path = ROOT / "editions" / f"{DATE}.html"
    edition_path.parent.mkdir(parents=True, exist_ok=True)
    edition_path.write_text(html + "\n", encoding="utf-8")

    print("DAILY 2026-08-30 BUILT")
    print("Homepage stories:", len(selected), "Topic-more stories:", len(extras))
    print("Desk counts:", counts)
    print("Japan:", counts["japan"], ">= 8 PASS")
    print("TopFive:", top)

if __name__ == "__main__":
    main()
