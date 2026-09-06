#!/usr/bin/env python3
"""Promote the current verified Daily edition into Rolling Desk reservoirs.

The Daily edition is already verified editorial copy, but desk ownership is
resolved independently by the shared editorial-routing policy.  Relevance tags
must not become uncontrolled public cross-posts.  Before syncing the current
Daily we therefore remove retained stories from desks they no longer own, then
promote each story only to its resolved primary/specialist desk.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

from desk_freshness_policy import EXPECTED_DESKS, current_daily_dates, routed_slugs

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


def main() -> int:
    latest = load(LATEST)
    desk = load(DESK)
    latest_date = str(latest.get("date") or "")
    allowed = current_daily_dates()
    if latest_date not in allowed:
        print(f"DAILY_DESK_SYNC_SKIP stale_daily={latest_date!r} allowed={sorted(allowed)}")
        return 0

    desks = desk.setdefault("desks", {})

    # Clean old uncontrolled cross-posts first. Stories without any resolvable
    # ownership are left in place for recovery/retention tooling to inspect;
    # stories with resolved ownership may only remain on an owned desk.
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
            kept.append(raw)
        desks[slug] = kept

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
            before = [str(x.get("id") or "") for x in existing if isinstance(x, dict)]
            desks[slug] = merge_front(existing, story)
            after = [str(x.get("id") or "") for x in desks[slug] if isinstance(x, dict)]
            if after and after[0] == str(story.get("id")) and (not before or before[0] != after[0]):
                promoted[slug] += 1

    DESK.write_text(json.dumps(desk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    changed = {k: v for k, v in promoted.items() if v}
    print(f"DAILY_TO_DESK_SYNC_PASS edition={latest_date} promoted={changed} removed_misroutes={len(removed)}")
    if removed:
        print("DAILY_DESK_MISROUTES_REMOVED", removed[:100])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
