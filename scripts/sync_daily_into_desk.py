#!/usr/bin/env python3
"""Promote the current verified Daily edition into Rolling Desk reservoirs.

The Daily edition is already verified editorial copy, but desk ownership is
resolved independently by the shared editorial-routing policy. Relevance tags
must not become uncontrolled public cross-posts. Before syncing the current
Daily we therefore remove retained stories from desks they no longer own, then
promote each story only to its resolved hard-routing desk(s) and sort every
public desk newest-first by a real editorial timestamp.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from desk_freshness_policy import (
    EXPECTED_DESKS,
    current_daily_dates,
    editorial_story_time,
    routed_slugs,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LATEST = DATA / "latest.json"
DESK = DATA / "desk-latest.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def title_key(story):
    return " ".join(str(story.get("title") or "").split()).casefold()


def merge_front(existing, story):
    sid = str(story.get("id") or "").strip()
    title = title_key(story)
    kept = []
    for old in existing:
        if not isinstance(old, dict):
            continue
        if sid and str(old.get("id") or "").strip() == sid:
            continue
        if title and title_key(old) == title:
            continue
        kept.append(old)
    return [story] + kept


def newest_first(stories):
    current = datetime.now(timezone.utc)

    def key(story):
        if not isinstance(story, dict):
            return float("-inf")
        stamp = editorial_story_time(story, now=current)
        return stamp.timestamp() if stamp is not None else float("-inf")

    return sorted(stories, key=key, reverse=True)


def main() -> int:
    latest = load(LATEST)
    desk = load(DESK)
    latest_date = str(latest.get("date") or "")
    allowed = current_daily_dates()
    if latest_date not in allowed:
        print(f"DAILY_DESK_SYNC_SKIP stale_daily={latest_date!r} allowed={sorted(allowed)}")
        return 0

    desks = desk.setdefault("desks", {})

    removed = []
    for slug in EXPECTED_DESKS:
        kept = []
        for raw in desks.setdefault(slug, []):
            if not isinstance(raw, dict):
                continue
            routes = routed_slugs(raw)
            if routes and slug not in routes:
                removed.append((slug, str(raw.get("id") or raw.get("title") or "unknown"), tuple(routes)))
                continue
            normalized = copy.deepcopy(raw)
            normalized["deskSlugs"] = list(dict.fromkeys(routes)) if routes else normalized.get("deskSlugs", [])
            kept.append(normalized)
        desks[slug] = newest_first(kept)

    promoted = {slug: 0 for slug in EXPECTED_DESKS}
    for raw in latest.get("articles") or []:
        if not isinstance(raw, dict) or not raw.get("id") or not raw.get("title"):
            continue
        slugs = routed_slugs(raw)
        if not slugs:
            continue
        for slug in slugs:
            story = copy.deepcopy(raw)
            story["status"] = "LATEST"
            story["deskSlugs"] = list(dict.fromkeys(slugs))
            story["desk"] = slug if len(slugs) == 1 else story.get("desk", slug)
            existing = desks.setdefault(slug, [])
            before_top = str(existing[0].get("id") or "") if existing and isinstance(existing[0], dict) else ""
            desks[slug] = newest_first(merge_front(existing, story))
            after_top = str(desks[slug][0].get("id") or "") if desks[slug] and isinstance(desks[slug][0], dict) else ""
            if after_top == str(story.get("id")) and before_top != after_top:
                promoted[slug] += 1

    for slug in EXPECTED_DESKS:
        desks[slug] = newest_first(desks.get(slug, []))

    DESK.write_text(json.dumps(desk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    changed = {k: v for k, v in promoted.items() if v}
    print(f"DAILY_TO_DESK_SYNC_PASS edition={latest_date} promoted={changed} removed_misroutes={len(removed)} newest_first=true")
    if removed:
        print("DAILY_DESK_MISROUTES_REMOVED", removed[:100])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
