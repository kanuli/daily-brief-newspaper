#!/usr/bin/env python3
"""Editor-in-Chief freshness recovery for verified topic-desk events.

This helper is intentionally publication-only: it never creates a Live edition.
It adds vetted current events to stale specialist desks before the existing
freshness/publication validators run. Same IDs are idempotent across retries.
"""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK_PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))
SLA_HOURS = {"ai-tech": 12, "manga-anime": 24}

RECOVERY = {
    "ai-tech": {
        "id": "ai-tech-seattle-times-newsday-openai-microsoft-lawsuit-20260907",
        "desk": "ai-tech",
        "deskSlugs": ["ai-tech"],
        "section": "AI／科技｜生成式AI／版權",
        "status": "LATEST",
        "title": "《Seattle Times》與Newsday控告OpenAI、微軟，指未經授權使用新聞內容訓練AI",
        "dek": "兩家美國報章在聯邦法院提出版權訴訟，爭議集中於生成式AI訓練、內容重現與新聞機構授權權益。",
        "summary": "《Seattle Times》與Newsday已入稟美國聯邦法院，控告OpenAI及Microsoft侵犯版權，指其新聞內容被未經授權用於訓練及支援生成式AI產品。被告方尚須在訴訟程序中正式回應及抗辯。",
        "body": "《Seattle Times》與Newsday已在紐約南區聯邦法院控告OpenAI及Microsoft，指兩家公司未經授權複製新聞內容，用於訓練、微調或支援生成式人工智能產品。原告亦指部分AI輸出會重現或近似其受版權保護內容，案件把新聞機構與AI公司的授權、訓練數據及合理使用爭議再次推上法院。\n\n路透社及《The Verge》均報道今次訴訟。現階段有關侵權、數據取得方式及損害的內容屬原告指控，仍待法院審理；案件的重要性在於它延續美國出版商就生成式AI訓練資料來源提出的法律挑戰，並可能影響科技公司與新聞機構日後的授權模式。",
        "context": "美國多家出版商與創作者近年先後就生成式AI訓練使用受版權保護內容提出訴訟，法院仍在建立相關法律界線。",
        "why": "案件直接涉及大型生成式AI供應商、訓練數據版權及新聞內容授權，主要新聞價值屬AI／科技治理與產品風險。",
        "watchNext": "留意OpenAI與Microsoft的正式答辯、法院會否處理模型或訓練數據相關禁制要求，以及同類案件對AI內容授權市場的影響。",
        "sourceName": "Reuters",
        "sourceUrl": "https://www.reuters.com/legal/government/seattle-times-newsday-sue-openai-microsoft-alleging-copyright-infringement-2026-09-05/",
        "timeLabel": "9月7日09:20 HKT前核實",
        "publishedAt": "2026-09-07T08:50:00+08:00",
        "sources": [
            {"name": "Reuters", "url": "https://www.reuters.com/legal/government/seattle-times-newsday-sue-openai-microsoft-alleging-copyright-infringement-2026-09-05/"},
            {"name": "The Verge", "url": "https://www.theverge.com/ai-artificial-intelligence/990932/seattle-times-newsday-lawsuit-openai-microsoft"}
        ]
    },
    "manga-anime": {
        "id": "manga-anime-hunter-x-hunter-420-next-publication-tbd-20260907",
        "desk": "manga-anime",
        "deskSlugs": ["manga-anime"],
        "section": "漫畫／動漫｜漫畫連載",
        "status": "LATEST",
        "title": "《HUNTER×HUNTER》第420話刊出，下一次刊載日期仍待《Jump》公布",
        "dek": "9月7日發售的《週刊少年Jump》刊出第420話；誌面告知下一次刊載安排將在確定後公布。",
        "summary": "《HUNTER×HUNTER》第420話已於9月7日發售的《週刊少年Jump》刊出，今輪由第411話起累計刊載10話；誌面表示下一次刊載日期尚未確定，確定後會在本誌公布。",
        "body": "《HUNTER×HUNTER》第420話已在9月7日發售的《週刊少年Jump》刊出。ORICON報道指，今輪由第411話開始至第420話合共刊載10話，而最新一期最後一頁列明，下一次刊載安排會在確定後於本誌公布，因此目前未有第421話的正式刊載日期。\n\n作品早已改為非固定周刊連載形式，故本次應準確表述為「下一次刊載日期待定」，而不是把未公布時間寫成固定休刊期。集英社相關章節頁亦已列出第420話，今次更新屬作品正式刊載進度，與一般宣傳或周邊商品消息不同。",
        "context": "《HUNTER×HUNTER》近年採非固定周刊刊載方式；作者冨樫義博持續公開原稿進度，但實際刊載時間以出版社正式安排為準。",
        "why": "第420話正式刊出及下一次刊載日期待定，直接影響核心漫畫作品的出版進度，屬Manga/Anime desk的當日實質新聞。",
        "watchNext": "留意《週刊少年Jump》或集英社何時公布第421話刊載安排，以及作者後續原稿進度是否轉化為正式出版日期。",
        "sourceName": "ORICON NEWS",
        "sourceUrl": "https://www.oricon.co.jp/news/2478698/",
        "timeLabel": "9月7日07:38 JST報道／09:20 HKT前核實",
        "publishedAt": "2026-09-07T07:38:00+09:00",
        "sources": [
            {"name": "ORICON NEWS", "url": "https://www.oricon.co.jp/news/2478698/"},
            {"name": "Shueisha chapter listing", "url": "https://mangaplus.shueisha.tv/truyen-tranh/hunter-x-hunter-144-en"}
        ]
    }
}


def parse_time(value):
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def newest_age_hours(stories, now):
    times = []
    for story in stories:
        parsed = parse_time(story.get("publishedAt"))
        if parsed:
            times.append(parsed.astimezone(HKT))
    if not times:
        return float("inf")
    return (now - max(times)).total_seconds() / 3600


def main():
    data = json.loads(DESK_PATH.read_text(encoding="utf-8"))
    desks = data.setdefault("desks", {})
    now = dt.datetime.now(HKT)
    changed = False

    for slug, story in RECOVERY.items():
        current = desks.setdefault(slug, [])
        if any(str(item.get("id")) == story["id"] for item in current):
            print(f"DESK_FRESHNESS_RECOVERY_PRESENT slug={slug} id={story['id']}")
            continue
        age = newest_age_hours(current, now)
        if age <= SLA_HOURS[slug]:
            print(f"DESK_FRESHNESS_RECOVERY_SKIP slug={slug} age_h={age:.2f} sla_h={SLA_HOURS[slug]}")
            continue
        current.insert(0, story)
        changed = True
        print(f"DESK_FRESHNESS_RECOVERY_ADD slug={slug} age_h={age:.2f} id={story['id']}")

    if changed:
        DESK_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("DESK_FRESHNESS_RECOVERY_APPLIED")
    else:
        print("DESK_FRESHNESS_RECOVERY_NOOP")


if __name__ == "__main__":
    main()
