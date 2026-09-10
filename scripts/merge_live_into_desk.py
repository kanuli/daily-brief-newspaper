#!/usr/bin/env python3
import copy
import json
import pathlib
import re
from datetime import datetime, timezone

from desk_retention import keep_on_desk
from desk_freshness_policy import editorial_story_time, routed_slugs

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIVE = DATA / "live.json"
DESK = DATA / "desk-latest.json"
MIN_BODY_MEASURE = 95

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
DESK_LABELS = {
    "world": "世界", "asia": "亞洲", "hong-kong": "香港", "japan": "日本",
    "market-economy": "財經 / 全球市場", "ai-tech": "AI / 科技",
    "manga-anime": "漫畫 / Anime", "manchester-united": "Manchester United",
    "football": "Football",
}
RETIRED_EVENT_IDS = {
    "world-lebanon-israel-strikes-four-killed-20260906-2000",
    "japan-motosu-cake-shop-arson-investigation-20260906-2000",
}
REQUIRED = (
    "title", "dek", "summary", "body", "context", "why", "watchNext",
    "sourceName", "sourceUrl", "timeLabel",
)
FORBIDDEN = re.compile(
    r"本輪(?:發布|更新|檢查|搜尋|核實|候選|稿件|新聞)|本報訊|incremental|duplicate|重複刊登|coverage\s*(?:check|test)|"
    r"collection\s*(?:design|test)|這次重新檢查|之後每一輪|每一輪Football|"
    r"固定檢查HKFA|不應由全球搜尋排名決定", re.I,
)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def body_measure(value):
    text = str(value or "")
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    return cjk if cjk >= 50 else len(re.sub(r"\s+", "", text))


def normalize_retained_story(story):
    if not isinstance(story, dict):
        return story
    body = str(story.get("body") or "").strip()
    if body_measure(body) >= MIN_BODY_MEASURE:
        return story
    additions = []
    existing = re.sub(r"\s+", "", body)
    for key in ("context", "why"):
        text = str(story.get(key) or "").strip()
        if text and re.sub(r"\s+", "", text) not in existing:
            additions.append(text)
            existing += re.sub(r"\s+", "", text)
        candidate = body + ("\n\n" if body and additions else "") + " ".join(additions)
        if body_measure(candidate) >= MIN_BODY_MEASURE:
            break
    if additions:
        story["body"] = body + ((" " if "\n\n" in body else "\n\n")) + " ".join(additions)
    return story


def desk_slugs(item):
    return routed_slugs(item)


def normalize_live_route(item):
    slugs = desk_slugs(item)
    if not slugs:
        raise SystemExit(f"Live item {item.get('id')} has no valid editorial route")
    primary = slugs[0]
    item["desk"] = primary
    item["deskSlugs"] = list(dict.fromkeys(slugs))
    if not str(item.get("section") or "").strip():
        item["section"] = DESK_LABELS.get(primary, "Live")
    if not str(item.get("sectionLabel") or "").strip():
        item["sectionLabel"] = item.get("section") or DESK_LABELS.get(primary, "Live")
    return slugs


def story_identity(story):
    story_id = str(story.get("id") or "").strip()
    if story_id:
        return "id:" + story_id
    return "title:" + re.sub(r"\s+", " ", str(story.get("title") or "")).strip().lower()


def dedupe(stories):
    out, seen, seen_titles = [], set(), set()
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


def newest_first(stories):
    current = datetime.now(timezone.utc)

    def key(story):
        if not isinstance(story, dict):
            return float("-inf")
        stamp = editorial_story_time(story, now=current)
        return stamp.timestamp() if stamp is not None else float("-inf")

    return sorted(dedupe(stories), key=key, reverse=True)


def unique_count(stories):
    return len(dedupe(stories))


def repair_required_cross_posts(desks):
    """Restore only cross-posts explicitly required by canonical routing.

    At present this principally guarantees Manchester United stories appear on
    both Manchester United and Football. It never creates a generic geographic
    or finance duplicate because routed_slugs() returns one desk for ordinary
    stories and specialist ownership overrides generic tags.
    """
    pool = {}
    for slug in FLOORS:
        for story in desks.get(slug, []):
            if isinstance(story, dict):
                pool.setdefault(story_identity(story), story)
    for story in pool.values():
        routes = list(dict.fromkeys(routed_slugs(story)))
        for slug in routes:
            if slug not in FLOORS or not keep_on_desk(story, slug):
                continue
            candidate = copy.deepcopy(story)
            candidate["deskSlugs"] = routes
            desks[slug] = newest_first([candidate] + desks.get(slug, []))


def routing_integrity(desks):
    """Verify the repaired public desk state against canonical routing policy.

    This is deliberately derived after stale cross-post removal and full
    re-sorting. A raw Live producer can start with zero desk counts, so its
    pre-merge geographic/routing flags are not evidence for the rendered desk
    state. Manchester United is the only intentional two-desk publication and
    is required on both Manchester United and Football by routed_slugs().
    """
    observed = {}
    expected = {}
    for slug in FLOORS:
        for story in desks.get(slug, []):
            if not isinstance(story, dict):
                return False
            ident = story_identity(story)
            routes = set(routed_slugs(story))
            if not routes or slug not in routes:
                return False
            observed.setdefault(ident, set()).add(slug)
            expected.setdefault(ident, set()).update(routes)
    return all(observed.get(ident, set()) == routes for ident, routes in expected.items())


def main():
    live = load(LIVE)
    desk = load(DESK)
    desks = desk.setdefault("desks", {})
    expired_cross_posts = []

    current_routes = {}
    for item in live.get("items", []):
        if isinstance(item, dict):
            current_routes[story_identity(item)] = set(desk_slugs(item))

    for slug in FLOORS:
        retained = []
        for raw in desks.setdefault(slug, []):
            if not isinstance(raw, dict):
                continue
            raw_id = str(raw.get("id") or "").strip()
            if raw_id in RETIRED_EVENT_IDS:
                expired_cross_posts.append((slug, raw_id))
                continue
            ident = story_identity(raw)
            desired_routes = set(routed_slugs(raw))
            if ident in current_routes:
                desired_routes = current_routes[ident]
            if not desired_routes or slug not in desired_routes:
                expired_cross_posts.append((slug, str(raw.get("id") or raw.get("title") or "unknown")))
                continue
            if not keep_on_desk(raw, slug):
                expired_cross_posts.append((slug, str(raw.get("id") or raw.get("title") or "unknown")))
                continue
            normalized = normalize_retained_story(copy.deepcopy(raw))
            normalized["deskSlugs"] = list(routed_slugs(normalized))
            retained.append(normalized)
        desks[slug] = newest_first(retained)

    for item in live.get("items", []):
        slugs = normalize_live_route(item)
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

        for slug in slugs:
            if not keep_on_desk(item, slug):
                expired_cross_posts.append((slug, str(item.get("id") or item.get("title") or "unknown")))
                continue
            story = normalize_retained_story(copy.deepcopy(item))
            story["status"] = "LATEST"
            story["deskSlugs"] = list(dict.fromkeys(slugs))
            existing = desks[slug]
            story_id = str(story.get("id") or "")
            story_title = re.sub(r"\s+", " ", str(story.get("title") or "")).strip().lower()
            existing = [s for s in existing
                        if str(s.get("id") or "") != story_id
                        and re.sub(r"\s+", " ", str(s.get("title") or "")).strip().lower() != story_title]
            desks[slug] = newest_first([story] + existing)

    repair_required_cross_posts(desks)
    for slug in FLOORS:
        desks[slug] = newest_first(desks.get(slug, []))

    counts = {slug: unique_count(desks.get(slug, [])) for slug in FLOORS}
    missing = {slug: (counts[slug], minimum) for slug, minimum in FLOORS.items() if counts[slug] < minimum}
    if missing:
        raise SystemExit(f"topic desk depth below hard floor: {missing}")

    routing_gate = routing_integrity(desks)
    if not routing_gate:
        raise SystemExit("public desk routing integrity failed after merge")

    desk["date"] = live.get("date", desk.get("date"))
    desk["generatedAt"] = live.get("lastUpdated")
    desk["mode"] = "ROLLING_DESK_LATEST"
    desk["editorialStandardVersion"] = 3
    desk["contentVersion"] = 3

    coverage = live.setdefault("coverage", {})
    coverage.pop("qaNote", None)
    depth_met = all(counts[slug] >= minimum for slug, minimum in FLOORS.items())
    source_gate = bool(coverage.get("sourceGateMet", coverage.get("sourceGate", False)))
    # Geographic/routing readiness must describe the repaired publication
    # state, not the raw producer snapshot. The merge has recalculated every
    # route, removed unrelated cross-posts, and routing_integrity() requires
    # observed public ownership to exactly match canonical routed_slugs().
    geographic_gate = routing_gate
    football_gate = counts["football"] >= FLOORS["football"]
    publication_ready = depth_met and source_gate and geographic_gate and football_gate
    coverage["deskLatestStoryCounts"] = counts
    coverage["deskLatestDepthMet"] = depth_met
    coverage["japanCountVerified"] = counts["japan"]
    coverage["sourceGateMet"] = source_gate
    coverage["routingGateMet"] = routing_gate
    coverage["geographicGateMet"] = geographic_gate
    coverage["footballGateMet"] = football_gate
    coverage["publishingGateMet"] = publication_ready
    coverage["status"] = "DAILY_BASELINE" if str(live.get("mode") or "").upper() == "DAILY_BASELINE" else ("COMPLETE" if publication_ready else "INCOMPLETE")
    if publication_ready:
        coverage.pop("blockingIssues", None)

    DESK.write_text(json.dumps(desk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LIVE.write_text(json.dumps(live, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if expired_cross_posts:
        print("ROLLING DESK EXPIRED CROSS-POSTS", expired_cross_posts)
    print("ROLLING DESK MERGE OK", counts)


if __name__ == "__main__":
    main()
