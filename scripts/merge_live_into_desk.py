#!/usr/bin/env python3
import copy
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIVE = DATA / "live.json"
DESK = DATA / "desk-latest.json"

# Public topic-page floors. These are minimums, never display caps.
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
# Keep enough rolling inventory for high-volume desks. Live/topFive limits must
# never truncate the retained topic pages.
CAPS = {
    "world": 24,
    "asia": 24,
    "hong-kong": 16,
    "japan": 20,
    "market-economy": 20,
    "ai-tech": 20,
    "manga-anime": 12,
    "manchester-united": 10,
    "football": 24,
}
DESK_ALIASES = {
    "world": ["world"],
    "asia": ["asia"],
    "hong-kong": ["hong-kong"],
    "japan": ["japan"],
    "finance": ["market-economy"],
    "market-economy": ["market-economy"],
    "ai-tech": ["ai-tech"],
    "manga-anime": ["manga-anime"],
    "manchester-united": ["manchester-united"],
    "football": ["football"],
    "stock-news": [],
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


def desk_slugs(item):
    explicit = item.get("deskSlugs")
    if isinstance(explicit, list) and explicit:
        return list(dict.fromkeys(str(slug) for slug in explicit if slug in FLOORS))
    return DESK_ALIASES.get(str(item.get("desk") or ""), [])


def story_identity(story):
    story_id = str(story.get("id") or "").strip()
    if story_id:
        return "id:" + story_id
    return "title:" + re.sub(r"\s+", " ", str(story.get("title") or "")).strip().lower()


def dedupe(stories):
    out = []
    seen = set()
    seen_titles = set()
    for story in stories:
        ident = story_identity(story)
        title = re.sub(r"\s+", " ", str(story.get("title") or "")).strip().lower()
        if ident in seen or (title and title in seen_titles):
            continue
        seen.add(ident)
        if title:
            seen_titles.add(title)
        out.append(story)
    return out


def unique_count(stories):
    return len(dedupe(stories))


def main():
    live = load(LIVE)
    desk = load(DESK)
    desks = desk.setdefault("desks", {})
    for slug in FLOORS:
        desks[slug] = dedupe(desks.setdefault(slug, []))[:CAPS[slug]]

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

        slugs = desk_slugs(item)
        for slug in slugs:
            story = copy.deepcopy(item)
            story["status"] = "LATEST"
            story["deskSlugs"] = list(dict.fromkeys(slugs))
            existing = desks[slug]
            story_id = str(story.get("id") or "")
            story_title = re.sub(r"\s+", " ", str(story.get("title") or "")).strip().lower()
            existing = [
                s for s in existing
                if str(s.get("id") or "") != story_id
                and re.sub(r"\s+", " ", str(s.get("title") or "")).strip().lower() != story_title
            ]
            desks[slug] = dedupe([story] + existing)[:CAPS[slug]]

    counts = {slug: unique_count(desks.get(slug, [])) for slug in FLOORS}
    missing = {slug: (counts[slug], minimum) for slug, minimum in FLOORS.items() if counts[slug] < minimum}
    if missing:
        raise SystemExit(f"topic desk depth below hard floor: {missing}")

    desk["date"] = live.get("date", desk.get("date"))
    desk["generatedAt"] = live.get("lastUpdated")
    desk["mode"] = "ROLLING_DESK_LATEST"
    desk["editorialStandardVersion"] = 3
    desk["contentVersion"] = 3

    coverage = live.setdefault("coverage", {})
    depth_met = all(counts[slug] >= minimum for slug, minimum in FLOORS.items())
    coverage["deskLatestStoryCounts"] = counts
    coverage["deskLatestDepthMet"] = depth_met
    coverage["japanCountVerified"] = counts["japan"]
    coverage["footballGateMet"] = counts["football"] >= FLOORS["football"]
    if depth_met and coverage.get("sourceGateMet", True) and coverage.get("geographicGateMet", True):
        coverage["status"] = "COMPLETE"
    else:
        coverage["status"] = "INCOMPLETE"

    DESK.write_text(json.dumps(desk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LIVE.write_text(json.dumps(live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ROLLING DESK MERGE OK", counts)


if __name__ == "__main__":
    main()
