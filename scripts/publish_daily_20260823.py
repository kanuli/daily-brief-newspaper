#!/usr/bin/env python3
import copy
import datetime as dt
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
TARGET_DATE = "2026-08-23"
TARGET_PUBLICATION = "2026-08-23T08:00:00+08:00"
EDITION = "004"


def run(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_branch(branch):
    subprocess.run(["git", "fetch", "origin", f"{branch}:refs/remotes/origin/{branch}"], cwd=ROOT, check=True, stdout=subprocess.DEVNULL)


def branch_json(branch, path):
    return json.loads(run("git", "show", f"refs/remotes/origin/{branch}:{path}"))


def story_extra_canada():
    return {
      "id":"world-canada-tariffs-0800","desk":"world","section":"世界｜北美／美加貿易",
      "title":"美加貿易談判破裂，美國50%關稅生效；加拿大宣布9月8日起對等反制",
      "dek":"新一輪關稅覆蓋約200億美元加拿大商品，渥太華將對美國鋼鐵、電子產品等採取等額回應。",
      "summary":"美國在談判未能達成協議後，對一批加拿大商品加徵50%關稅；加拿大總理Mark Carney宣布9月8日起推出對等反制。",
      "body":"美加貿易摩擦在周末進一步升級。美國在雙邊談判未能取得協議後，對約200億美元加拿大商品加徵50%關稅，涉及規模約佔加拿大對美出口5%。加拿大政府隨即宣布會以等額方式回應，反制措施預定9月8日起生效，範圍包括鋼鐵、電子產品及其他美國貨品。\n\n新的關稅衝突直接增加北美跨境供應鏈、企業成本與消費價格的不確定性，也令下一輪USMCA相關談判更複雜。汽車、金屬、農業與製造業高度依賴美加一體化供應鏈，若雙方再擴大清單，企業可能加快調整採購、庫存及生產布局。",
      "context":"美國與加拿大是彼此最重要的貿易伙伴之一，供應鏈在汽車、能源、金屬及農產品領域高度整合。",
      "why":"50%關稅與對等反制會影響北美物價、企業利潤與跨境投資，亦可能成為全球貿易風險的新來源。",
      "watchNext":"留意加拿大公布完整反制清單、美方是否再擴大措施，以及USMCA談判能否重啟。",
      "sourceName":"Associated Press","sourceUrl":"https://apnews.com/article/4d18583fe52134ca8550652ad9772d2c",
      "timeLabel":"23 Aug 2026 · 早上更新",
      "sources":[
        {"name":"Associated Press","url":"https://apnews.com/article/4d18583fe52134ca8550652ad9772d2c"},
        {"name":"Reuters","url":"https://www.investing.com/news/world-news/canada-to-impose-retaliatory-tariffs-across-a-raft-of-us-sectors-carney-says-4872377"}
      ]
    }


def story_extra_japan():
    return {
      "id":"japan-russia-kurils-drill-0800","desk":"japan","section":"日本｜外交／北方領土",
      "title":"俄羅斯在爭議北方四島周邊發射反艦導彈，日本抗議軍事部署升級",
      "dek":"俄太平洋艦隊由擇捉島發射Bastion岸基反艦導彈，演習涉及艦艇、潛艇、飛機及逾萬名軍人。",
      "summary":"俄羅斯在日本稱為北方領土的爭議島嶼附近舉行大規模軍演並發射導彈，日本政府表示強烈反對。",
      "body":"俄羅斯太平洋艦隊近期在爭議千島群島南部一帶舉行大規模演習，並從擇捉島發射Bastion岸基反艦導彈，模擬攻擊海上目標。演習涉及約60艘艦艇與潛艇、30架飛機及逾13,000名軍人，俄羅斯總統普京亦曾到訪相關島嶼。\n\n日本把這些島嶼稱為北方領土，長期主張主權，並反對俄方加強軍事部署。日本外相茂木敏充批評演習與日本立場相抵觸；在日俄關係因烏克蘭戰爭與制裁持續低迷之際，軍演再增加北海道周邊安全與外交摩擦。",
      "context":"南千島群島／北方領土爭議自二戰結束後持續至今，日俄仍未簽署正式和平條約。",
      "why":"軍演把主權爭議與俄羅斯在太平洋的軍事存在重新拉到日本安全政策前線。",
      "watchNext":"留意演習是否延續至8月底、日本後續外交抗議及俄方在島嶼的軍事部署。",
      "sourceName":"The Guardian","sourceUrl":"https://www.theguardian.com/world/2026/aug/21/russia-launch-missiles-kuril-islands-japan",
      "timeLabel":"21–23 Aug 2026",
      "sources":[
        {"name":"The Guardian","url":"https://www.theguardian.com/world/2026/aug/21/russia-launch-missiles-kuril-islands-japan"},
        {"name":"Wall Street Journal","url":"https://www.wsj.com/world/asia/russian-missile-drills-stoke-tensions-with-japan-f0c62a31"}
      ]
    }


SECTION_NAMES = {
 "world":"世界｜歐洲／國際", "asia":"亞洲｜區內", "hong-kong":"香港｜本地", "japan":"日本｜社會",
 "finance":"財經／全球市場", "stock-news":"財經／Stock News", "ai-tech":"AI／科技",
 "manga-anime":"漫畫／Anime", "manchester-united":"Manchester United", "football":"Football",
}
DESK_SLUGS = {
 "world":["world"], "asia":["asia"], "hong-kong":["hong-kong"], "japan":["japan"],
 "finance":["market-economy"], "stock-news":["market-economy","ai-tech"], "ai-tech":["ai-tech"],
 "manga-anime":["manga-anime"], "manchester-united":["manchester-united","football"], "football":["football"],
}
FLOORS = {"world":4,"asia":5,"hong-kong":5,"japan":5,"market-economy":5,"ai-tech":4,"manga-anime":3,"manchester-united":3,"football":6}


def normalize_article(a):
    x = copy.deepcopy(a)
    x.setdefault("section", SECTION_NAMES.get(x.get("desk"), "新聞"))
    return x


def as_desk_story(a, slug):
    x = copy.deepcopy(a)
    x["status"] = "LATEST"
    x["deskSlugs"] = list(dict.fromkeys(DESK_SLUGS.get(x.get("desk"), []) + [slug]))
    return x


def main():
    now_hkt = dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
    if now_hkt.date().isoformat() != TARGET_DATE:
        print(f"daily corrective publisher: target {TARGET_DATE}; today {now_hkt.date().isoformat()} -> no-op")
        return 0

    fetch_branch("prepublish-news")
    fetch_branch("news-staging")
    draft = branch_json("prepublish-news", "data/prepublish.json")
    staging = branch_json("news-staging", "data/search-staging.json")
    if draft.get("status") != "VERIFIED_DRAFT":
        raise SystemExit("prepublish draft is not VERIFIED_DRAFT")
    if draft.get("publicationType") != "DAILY" or draft.get("targetPublication") != TARGET_PUBLICATION:
        raise SystemExit("prepublish draft does not target this Daily")
    if not staging.get("lastSearchAt"):
        raise SystemExit("rolling staging has no lastSearchAt")

    articles = [normalize_article(a) for a in draft.get("articles", [])]
    extras = [story_extra_canada(), story_extra_japan()]
    by_id = {a["id"]: a for a in articles}
    for extra in extras:
        by_id[extra["id"]] = extra
    ordered_ids = ["world-canada-tariffs-0800"] + [a["id"] for a in articles] + ["japan-russia-kurils-drill-0800"]
    articles = [by_id[i] for i in dict.fromkeys(ordered_ids)]
    if not (12 <= len(articles) <= 20):
        raise SystemExit(f"Daily requires 12-20 articles; got {len(articles)}")

    sections = [
      {"slug":"world","title":"世界","subtitle":"歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）","articleIds":["world-canada-tariffs-0800","world-russia-economic-targets-0800"]},
      {"slug":"asia","title":"亞洲","subtitle":"東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · 高加索 · 全亞洲","articleIds":["asia-iran-sanctions-0800","japan-russia-kurils-drill-0800"]},
      {"slug":"hong-kong","title":"香港","subtitle":"本地 · 社會 · 法庭 · 公共政策 · 民生","articleIds":["hk-dog-rules-review-0800"]},
      {"slug":"japan","title":"日本","subtitle":"社會 · 司法 · 政策 · 交通 · 教育 · 醫療 · 生活","articleIds":["japan-fuji-child-0800","japan-russia-kurils-drill-0800"]},
      {"slug":"market-economy","title":"📈 財經 / 全球市場","subtitle":"美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球","articleIds":["finance-bonds-oil-0800","stock-nvda-earnings-0800","world-canada-tariffs-0800"]},
      {"slug":"ai-tech","title":"AI / 科技","subtitle":"全球 AI · 半導體 · 雲端 · 軟件 · 網絡安全","articleIds":["ai-nvidia-server-price-0800","stock-nvda-earnings-0800"]},
      {"slug":"manga-anime","title":"漫畫 / Anime","subtitle":"動畫 · 漫畫 · 出版 · 製作 · 產業","articleIds":["anime-fate-strange-fake-new-series-0800"]},
      {"slug":"manchester-united","title":"Manchester United","subtitle":"Club · Squad · Matches · Transfers","articleIds":["mu-hull-loss-0800"]},
      {"slug":"football","title":"Football","subtitle":"Europe · UEFA · International · J-League · Hong Kong · Worldwide","articleIds":["mu-hull-loss-0800","football-taremi-al-wasl-0800"]},
    ]

    daily = {
      "editionNumber":EDITION,"date":TARGET_DATE,"dateLabel":"2026年8月23日 星期日",
      "tagline":"全球更新 · Overnight Rolling · v3長文","editorialStandardVersion":3,"contentVersion":3,
      "leadId":"world-canada-tariffs-0800",
      "topFive":["world-canada-tariffs-0800","world-russia-economic-targets-0800","asia-iran-sanctions-0800","mu-hull-loss-0800","ai-nvidia-server-price-0800"],
      "collectionAudit":{"rollingStagingLastSearchAt":staging.get("lastSearchAt"),"prepublishDraftId":draft.get("draftId"),"prepublishCreatedAt":draft.get("createdAt"),"verifiedDraftUsed":True},
      "articles":articles,"sections":sections
    }
    write_json(DATA / f"{TARGET_DATE}.json", daily)
    write_json(DATA / "latest.json", daily)

    prior_desk = load_json(DATA / "desk-latest.json")
    current_ids = {a["id"] for a in articles}
    more_articles, more_sections, seen = [], [], set()
    topic_titles = {"world":"世界","asia":"亞洲","hong-kong":"香港","japan":"日本","market-economy":"📈 財經 / 全球市場","ai-tech":"AI / 科技","manga-anime":"漫畫 / Anime","manchester-united":"Manchester United","football":"Football"}
    topic_subtitles = {
      "world":"歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）",
      "asia":"東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · 高加索 · 全亞洲",
      "hong-kong":"本地 · 社會 · 法庭 · 公共政策 · 民生","japan":"社會 · 司法 · 政策 · 交通 · 教育 · 醫療 · 生活",
      "market-economy":"美國 · 歐洲 · 亞洲 · 全球市場","ai-tech":"全球 AI · 半導體 · 雲端 · 軟件 · 網絡安全",
      "manga-anime":"動畫 · 漫畫 · 出版 · 製作 · 產業","manchester-united":"Club · Squad · Matches · Transfers",
      "football":"Europe · UEFA · International · J-League · Hong Kong · Worldwide",
    }
    for slug in FLOORS:
        chosen = []
        for s in prior_desk.get("desks", {}).get(slug, []):
            sid = s.get("id")
            if not sid or sid in current_ids or sid in seen:
                continue
            more_articles.append(copy.deepcopy(s)); chosen.append(sid); seen.add(sid)
            if len(chosen) >= 1:
                break
        more_sections.append({"slug":slug,"title":topic_titles[slug],"subtitle":topic_subtitles[slug],"articleIds":chosen})
    write_json(DATA / "topic-more" / f"{TARGET_DATE}.json", {"date":TARGET_DATE,"editorialStandardVersion":3,"contentVersion":3,"articles":more_articles,"sections":more_sections})

    desks = copy.deepcopy(prior_desk.get("desks", {}))
    incoming = {slug: [] for slug in FLOORS}
    for a in articles:
        for slug in DESK_SLUGS.get(a.get("desk"), []):
            if slug in incoming:
                incoming[slug].append(as_desk_story(a, slug))
    incoming["market-economy"].append(as_desk_story(story_extra_canada(), "market-economy"))
    incoming["asia"].append(as_desk_story(story_extra_japan(), "asia"))
    for slug, minimum in FLOORS.items():
        merged, ids = [], set()
        for s in incoming[slug] + desks.get(slug, []):
            sid = s.get("id")
            if not sid or sid in ids:
                continue
            x = copy.deepcopy(s); x["status"] = "LATEST"; x["deskSlugs"] = list(dict.fromkeys(list(x.get("deskSlugs") or []) + [slug]))
            merged.append(x); ids.add(sid)
        desks[slug] = merged[:max(minimum, min(len(merged), minimum + 2))]
        if len(desks[slug]) < minimum:
            raise SystemExit(f"desk {slug} below depth floor {len(desks[slug])} < {minimum}")
    write_json(DATA / "desk-latest.json", {"date":TARGET_DATE,"generatedAt":TARGET_PUBLICATION,"mode":"ROLLING_DESK_LATEST","editorialStandardVersion":3,"contentVersion":3,"desks":desks})

    vocab = {
      "date":TARGET_DATE,"sourceRepo":"kanuli/japanese-vocab-game","sourceFile":"data/advanced_vocab.js","sourceUrl":"https://github.com/kanuli/japanese-vocab-game","levelNote":"資料中的部分 JLPT 分級為推定，並非官方 JLPT 詞表。",
      "words":[
        {"level":"N1","reading":"けんじ","kanji":"検事","meaning":"檢察官","partOfSpeech":"noun"},{"level":"N1","reading":"しんりゃく","kanji":"侵略","meaning":"侵略","partOfSpeech":"verb"},
        {"level":"N2","reading":"てくび","kanji":"手首","meaning":"手腕、手腕部","partOfSpeech":"noun"},{"level":"N2","reading":"しょうきん","kanji":"賞金","meaning":"賞金、獎金","partOfSpeech":"noun"},
        {"level":"N3","reading":"しょうぼう","kanji":"消防","meaning":"消防","partOfSpeech":"noun"},{"level":"N3","reading":"どくしん","kanji":"独身","meaning":"單身、未婚","partOfSpeech":"adj"},
        {"level":"N4","reading":"まず","kanji":"先ず","meaning":"首先、最初","partOfSpeech":"adv"},{"level":"N4","reading":"いっぱい","kanji":"一杯","meaning":"很多、滿滿","partOfSpeech":"adj"},
        {"level":"N5","reading":"ちょうど","kanji":"丁度","meaning":"正好、恰好","partOfSpeech":"adv"},{"level":"N5","reading":"どこ","kanji":"何処","meaning":"哪裡、哪個地方","partOfSpeech":"other"}
      ]
    }
    write_json(DATA / "vocab" / f"{TARGET_DATE}.json", vocab)

    archive = load_json(DATA / "archive.json")
    old = [e for e in archive.get("editions", []) if e.get("date") != TARGET_DATE]
    entry = {"date":TARGET_DATE,"shortDate":"23 AUG 2026","headline":"美加貿易戰升級；俄烏經濟設施互襲；曼聯開季0：2負Hull","topics":["世界","亞洲","香港","日本","財經 / 全球市場","AI / 科技","漫畫 / Anime","Manchester United","Football","日語學習"],"url":f"editions/{TARGET_DATE}.html"}
    write_json(DATA / "archive.json", {"editions":[entry] + old})

    live = {"mode":"daily-baseline","date":TARGET_DATE,"editorialStandardVersion":3,"contentVersion":3,"lastUpdated":TARGET_PUBLICATION,"lastUpdatedLabel":"2026年8月23日 08:00 HKT","nextUpdateLabel":"下一輪預定 09:00 HKT","windowLabel":"Daily Edition baseline","newCount":0,"updatedCount":0,"developingCount":0,"coverage":{"status":"DAILY_BASELINE","baselineAt":TARGET_PUBLICATION,"qaNote":"08:00 Daily publication baseline; no separate Live hourly edition."},"items":[]}
    write_json(DATA / "live.json", live)

    template = (ROOT / "editions" / "2026-08-22.html").read_text(encoding="utf-8")
    html = template.replace("2026-08-22", TARGET_DATE).replace("2026年8月22日", "2026年8月23日").replace("NO. <span data-edition-number>003</span>", "NO. <span data-edition-number>004</span>").replace("全球更新 · v3長文 · 多來源核實", "全球更新 · Overnight Rolling · v3長文").replace("v=20260822", "v=20260823")
    (ROOT / "editions" / f"{TARGET_DATE}.html").write_text(html, encoding="utf-8")

    print(f"Prepared Daily {TARGET_DATE}: {len(articles)} front-page stories; staging through {staging.get('lastSearchAt')}")
    print("Desk counts:", {k: len(v) for k,v in desks.items()})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
