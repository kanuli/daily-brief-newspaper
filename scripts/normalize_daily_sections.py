#!/usr/bin/env python3
"""Repair a missing/invalid Daily v3 sections index from the article payload itself.

This is schema normalization only. It never invents stories, timestamps, sources,
or copy. Existing valid section arrays are preserved unchanged.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

SECTION_META = [
    ("world", "世界", "歐洲、美洲、非洲、大洋洲與跨區國際要聞"),
    ("asia", "亞洲", "東亞、東南亞、南亞、中亞、西亞／中東"),
    ("hong-kong", "香港", "香港社會、政策、經濟與公共事務"),
    ("japan", "日本", "日本社會、政治、經濟與公共事務"),
    ("market-economy", "財經", "市場、宏觀經濟、企業與產業"),
    ("ai-tech", "AI／科技", "人工智能、科技、科研與數碼產業"),
    ("manga-anime", "漫畫／Anime", "漫畫、動畫與相關產業"),
    ("manchester-united", "Manchester United", "曼聯球隊、賽事、轉會與傷兵"),
    ("football", "Football", "全球足球賽事、球隊、轉會、傷兵與規例"),
]


def classify(story: dict) -> list[str]:
    section = str(story.get("section") or "").strip()
    sid = str(story.get("id") or "").strip().lower()
    head = section.split("｜", 1)[0].strip().lower()

    if head.startswith("manchester united") or sid.startswith("manchester-united-"):
        return ["manchester-united", "football"]
    if head.startswith("football") or sid.startswith("football-"):
        return ["football"]
    if head.startswith("漫畫") or "anime" in head or sid.startswith("manga-") or sid.startswith("anime-"):
        return ["manga-anime"]
    if head.startswith("香港") or sid.startswith("hong-kong-"):
        return ["hong-kong"]
    if head.startswith("日本") or sid.startswith("japan-"):
        return ["japan"]
    if head.startswith("亞洲") or sid.startswith("asia-"):
        return ["asia"]
    if head.startswith("世界") or sid.startswith("world-"):
        return ["world"]
    if head.startswith("ai") or "科技" in head or sid.startswith("ai-") or sid.startswith("tech-"):
        return ["ai-tech"]
    if head.startswith("財經") or head.startswith("市場") or sid.startswith("market-") or sid.startswith("finance-"):
        return ["market-economy"]
    raise ValueError(f"cannot classify Daily article {story.get('id')!r} section={section!r}")


def valid_existing(data: dict) -> bool:
    sections = data.get("sections")
    articles = data.get("articles")
    if not isinstance(sections, list) or not isinstance(articles, list):
        return False
    known = {a.get("id") for a in articles if isinstance(a, dict) and a.get("id")}
    if len(known) != len(articles):
        return False
    for sec in sections:
        if not isinstance(sec, dict) or not isinstance(sec.get("articleIds", []), list):
            return False
        if any(article_id not in known for article_id in sec.get("articleIds", [])):
            return False
    return True


def normalize(path: Path) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    if int(data.get("contentVersion", 1) or 1) < 3:
        return False
    if valid_existing(data):
        return False

    articles = data.get("articles")
    if not isinstance(articles, list) or not articles:
        raise ValueError(f"{path}: v3 Daily articles missing/invalid")

    buckets = {slug: [] for slug, _, _ in SECTION_META}
    seen = set()
    for story in articles:
        if not isinstance(story, dict) or not story.get("id"):
            raise ValueError(f"{path}: invalid article entry")
        article_id = story["id"]
        if article_id in seen:
            raise ValueError(f"{path}: duplicate article id {article_id}")
        seen.add(article_id)
        for slug in classify(story):
            buckets[slug].append(article_id)

    data["sections"] = [
        {
            "id": slug,
            "slug": slug,
            "title": title,
            "subtitle": subtitle,
            "articleIds": buckets[slug],
        }
        for slug, title, subtitle in SECTION_META
    ]
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"DAILY_SECTIONS_NORMALIZED {path.relative_to(ROOT)} counts=" + str({k: len(v) for k, v in buckets.items()}))
    return True


def main() -> int:
    latest = DATA / "latest.json"
    if not latest.exists():
        raise SystemExit("data/latest.json missing")
    changed = normalize(latest)
    data = json.loads(latest.read_text(encoding="utf-8"))
    date = str(data.get("date") or "").strip()
    if date:
        dated = DATA / f"{date}.json"
        if dated.exists():
            changed = normalize(dated) or changed
    print("DAILY_SECTIONS_NORMALIZER_PASS changed=" + str(changed).lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
