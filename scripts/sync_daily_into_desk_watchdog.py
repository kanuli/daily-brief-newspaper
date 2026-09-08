#!/usr/bin/env python3
"""Restore current Daily baseline stories into their routed Rolling Desks.

This is an idempotent publication repair helper. It does not create news; it
only propagates already-published Daily articles, preserving IDs and sources,
then sorts every touched desk by the shared editorial timestamp resolver.
"""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

from desk_freshness_policy import editorial_story_time, routed_slugs, current_daily_dates
from desk_retention import keep_on_desk

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LATEST = DATA / "latest.json"
DESK = DATA / "desk-latest.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def identity(story):
    sid = str(story.get("id") or "").strip()
    return ("id", sid) if sid else ("title", " ".join(str(story.get("title") or "").split()).lower())


def newest_first(stories):
    now = datetime.now(timezone.utc)
    seen = set()
    out = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        ident = identity(story)
        if ident in seen:
            continue
        seen.add(ident)
        out.append(story)
    def key(story):
        stamp = editorial_story_time(story, now=now)
        return stamp.timestamp() if stamp is not None else float("-inf")
    return sorted(out, key=key, reverse=True)


def main():
    latest = load(LATEST)
    desk = load(DESK)
    now = datetime.now(timezone.utc)
    if str(latest.get("date") or "") not in current_daily_dates(now=now):
        print("DAILY_DESK_SYNC_SKIP latest_not_current", latest.get("date"))
        return

    desks = desk.setdefault("desks", {})
    added = []
    for article in latest.get("articles") or []:
        if not isinstance(article, dict) or not str(article.get("id") or "").strip():
            continue
        routes = list(dict.fromkeys(routed_slugs(article)))
        for slug in routes:
            if slug not in desks or not isinstance(desks.get(slug), list):
                desks[slug] = []
            if not keep_on_desk(article, slug):
                continue
            aid = str(article["id"])
            if any(isinstance(s, dict) and str(s.get("id") or "") == aid for s in desks[slug]):
                continue
            story = copy.deepcopy(article)
            story["status"] = "LATEST"
            story["desk"] = routes[0] if routes else slug
            story["deskSlugs"] = routes
            desks[slug].append(story)
            added.append((slug, aid))

    for slug in list(desks):
        if isinstance(desks[slug], list):
            desks[slug] = newest_first(desks[slug])

    if added:
        DESK.write_text(json.dumps(desk, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("DAILY_DESK_SYNC_RESTORED", added)
    else:
        print("DAILY_DESK_SYNC_NOOP")


if __name__ == "__main__":
    main()
