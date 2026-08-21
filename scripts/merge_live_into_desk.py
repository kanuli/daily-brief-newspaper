#!/usr/bin/env python3
import copy
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIVE = DATA / "live.json"
DESK = DATA / "desk-latest.json"

FLOORS = {
    "world": 4,
    "asia": 5,
    "hong-kong": 5,
    "japan": 5,
    "market-economy": 5,
    "ai-tech": 4,
    "manga-anime": 3,
    "manchester-united": 3,
    "football": 6,
}
CAPS = {
    "world": 8,
    "asia": 10,
    "hong-kong": 8,
    "japan": 8,
    "market-economy": 10,
    "ai-tech": 8,
    "manga-anime": 6,
    "manchester-united": 6,
    "football": 12,
}
REQUIRED = (
    "title", "dek", "summary", "body", "context", "why", "watchNext",
    "sourceName", "sourceUrl", "timeLabel",
)
FORBIDDEN = re.compile(
    r"本輪|本報|incremental|duplicate|重複刊登|coverage\s*(?:check|test)|"
    r"collection\s*(?:design|test)|這次重新檢查|之後每一輪|每一輪Football|"
    r"固定檢查HKFA|不應由全球搜尋排名決定",
    re.I,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    live = load(LIVE)
    desk = load(DESK)
    desks = desk.setdefault("desks", {})
    for slug in FLOORS:
        desks.setdefault(slug, [])

    for item in live.get("items", []):
        for field in REQUIRED:
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise SystemExit(f"Live item {item.get('id')} missing {field}")
        paras = [p.strip() for p in re.split(r"\n\s*\n", item["body"]) if p.strip()]
        if len(paras) < 2:
            raise SystemExit(f"Live item {item.get('id')} body lacks 2 paragraphs")
        public = " ".join(str(item.get(k, "")) for k in (
            "title", "dek", "summary", "body", "context", "why", "watchNext"
        ))
        if FORBIDDEN.search(public):
            raise SystemExit(f"Live item {item.get('id')} contains process copy")

        for slug in item.get("deskSlugs", []):
            if slug not in desks:
                continue
            story = copy.deepcopy(item)
            story["status"] = "LATEST"
            desks[slug] = [s for s in desks[slug] if s.get("id") != story.get("id")]
            desks[slug].insert(0, story)
            desks[slug] = desks[slug][:CAPS[slug]]

    counts = {slug: len(desks.get(slug, [])) for slug in FLOORS}
    for slug, minimum in FLOORS.items():
        if counts[slug] < minimum:
            raise SystemExit(f"{slug} depth {counts[slug]} < {minimum}")

    desk["date"] = live.get("date", desk.get("date"))
    desk["generatedAt"] = live.get("lastUpdated")
    desk["mode"] = "ROLLING_DESK_LATEST"
    desk["editorialStandardVersion"] = 3
    desk["contentVersion"] = 3

    coverage = live.setdefault("coverage", {})
    coverage["deskLatestStoryCounts"] = counts
    coverage["deskLatestDepthMet"] = all(
        counts[slug] >= minimum for slug, minimum in FLOORS.items()
    )

    DESK.write_text(json.dumps(desk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LIVE.write_text(json.dumps(live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ROLLING DESK MERGE OK", counts)


if __name__ == "__main__":
    main()
