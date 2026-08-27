#!/usr/bin/env python3
"""Validate that every public topic desk contains current verified news.

A desk is unhealthy when its newest published story breaches the desk-specific
freshness SLA, even if the page still contains enough old stories to satisfy a
numeric depth floor. The validator also requires current Daily stories to have
propagated into their routed Rolling Desk reservoirs.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from desk_freshness_policy import (
    EXPECTED_DESKS,
    PUBLIC_DESK_FRESHNESS_HOURS,
    current_daily_dates,
    newest_age_hours,
    routed_slugs,
)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit(latest, desk, now):
    desks = desk.get("desks") if isinstance(desk.get("desks"), dict) else {}
    latest_date = str(latest.get("date") or "")
    daily_current = latest_date in current_daily_dates(now=now)

    daily_by_slug = {slug: [] for slug in EXPECTED_DESKS}
    if daily_current:
        for article in latest.get("articles") or []:
            if not isinstance(article, dict):
                continue
            aid = str(article.get("id") or "").strip()
            if not aid:
                continue
            for slug in routed_slugs(article):
                daily_by_slug[slug].append(aid)

    rows = {}
    failures = []
    for slug in EXPECTED_DESKS:
        stories = desks.get(slug) if isinstance(desks.get(slug), list) else []
        ids = {str(s.get("id") or "").strip() for s in stories if isinstance(s, dict)}
        age = newest_age_hours(stories, now=now)
        limit = PUBLIC_DESK_FRESHNESS_HOURS[slug]
        missing_daily = [aid for aid in daily_by_slug[slug] if aid not in ids]
        fresh = age is not None and age <= limit
        daily_synced = not missing_daily
        rows[slug] = {
            "storyCount": len(stories),
            "newestAgeHours": age,
            "freshnessSlaHours": limit,
            "fresh": fresh,
            "currentDailyArticleIds": daily_by_slug[slug],
            "missingCurrentDailyArticleIds": missing_daily,
            "dailySynced": daily_synced,
        }
        if not stories:
            failures.append(f"{slug}: empty desk")
        elif not fresh:
            failures.append(f"{slug}: newest story age {age!r}h exceeds {limit}h SLA")
        if daily_current and missing_daily:
            failures.append(f"{slug}: current Daily story/stories missing from Rolling Desk: {', '.join(missing_daily)}")

    return {
        "checkedAt": now.astimezone(timezone.utc).isoformat(),
        "latestDate": latest_date,
        "currentDaily": daily_current,
        "status": "PASS" if not failures else "FAIL",
        "desks": rows,
        "failures": failures,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", default=str(DATA / "latest.json"))
    ap.add_argument("--desk", default=str(DATA / "desk-latest.json"))
    ap.add_argument("--report")
    ap.add_argument("--now", help="ISO timestamp, test-only")
    args = ap.parse_args()
    now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    result = audit(load(Path(args.latest)), load(Path(args.desk)), now)
    if args.report:
        Path(args.report).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for slug, row in result["desks"].items():
        print(
            f"DESK_FRESHNESS slug={slug} stories={row['storyCount']} age_h={row['newestAgeHours']} "
            f"sla_h={row['freshnessSlaHours']} daily_missing={len(row['missingCurrentDailyArticleIds'])}"
        )
    if result["failures"]:
        for failure in result["failures"]:
            print("DESK_FRESHNESS_FAIL", failure)
        return 2
    print("DESK_FRESHNESS_PASS all_public_desks_current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
