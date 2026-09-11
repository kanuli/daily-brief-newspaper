#!/usr/bin/env python3
import datetime
import json
import pathlib
import re
import subprocess
import sys

from desk_freshness_policy import (
    PUBLIC_DESK_FRESHNESS_HOURS,
    editorial_story_time,
    newest_age_hours,
    routed_slugs,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REQUIRED_STORY_FIELDS = (
    "id", "title", "dek", "summary", "body", "context", "why",
    "watchNext", "sourceName", "sourceUrl", "timeLabel",
)
EXPECTED_DESKS = (
    "world", "asia", "hong-kong", "japan", "market-economy",
    "ai-tech", "manga-anime", "manchester-united", "football",
)
DEPTH_FLOOR = {
    "world": 8, "asia": 8, "hong-kong": 6, "japan": 8,
    "market-economy": 8, "ai-tech": 6, "manga-anime": 4,
    "manchester-united": 4, "football": 10,
}
MIN_BODY_MEASURE = 95


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def need(condition, message):
    if not condition:
        raise SystemExit(message)


def rich_story(story, label):
    need(isinstance(story, dict), f"{label}: story must be an object")
    for field in REQUIRED_STORY_FIELDS:
        value = story.get(field)
        need(isinstance(value, str) and value.strip(), f"{label}: missing {field}")
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", story["body"]) if p.strip()]
    need(len(paragraphs) >= 2, f"{label}: body needs at least two paragraphs")
    cjk = len(re.findall(r"[\u3400-\u9fff]", story["body"]))
    measure = cjk if cjk >= 50 else len(re.sub(r"\s+", "", story["body"]))
    need(measure >= MIN_BODY_MEASURE, f"{label}: body too short ({measure}; approx-100 floor={MIN_BODY_MEASURE})")


def publication_dates_align(latest_date, live_date):
    try:
        daily = datetime.date.fromisoformat(str(latest_date))
        live = datetime.date.fromisoformat(str(live_date))
    except (TypeError, ValueError):
        return False
    return live == daily or live == daily + datetime.timedelta(days=1)


def validate_live(latest, live, desk):
    mode = str(live.get("mode") or "").upper()
    need(mode in {"LIVE", "HOURLY_LIVE", "LIVE_INCREMENTAL", "LIVE_UPDATE", "DAILY_BASELINE"}, f"live mode invalid: {mode!r}")
    need(publication_dates_align(latest.get("date"), live.get("date")), "live date must match Daily date or immediate overnight handoff date")
    for key in ("lastUpdated", "lastUpdatedLabel", "windowLabel", "nextUpdateLabel"):
        need(isinstance(live.get(key), str) and live[key].strip(), f"live missing {key}")
    items = live.get("items")
    need(isinstance(items, list), "live items must be an array")
    coverage = live.get("coverage")
    need(isinstance(coverage, dict) and str(coverage.get("status", "")).strip(), "Live coverage.status required")

    if mode == "DAILY_BASELINE":
        need(live.get("date") == latest.get("date"), "Daily baseline date must equal current Daily date")
        need(items == [], "08:00 Daily baseline must not publish separate Live stories")
        need(live.get("newCount") == 0 and live.get("updatedCount") == 0 and live.get("developingCount") == 0, "Daily baseline counters must all be zero")
        counts = coverage.get("deskLatestStoryCounts")
        need(isinstance(counts, dict), "Daily baseline requires deskLatestStoryCounts")
        for slug, minimum in DEPTH_FLOOR.items():
            actual = len(desk.get("desks", {}).get(slug, []))
            need(actual >= minimum, f"Daily baseline desk {slug} depth {actual} < {minimum}")
            need(counts.get(slug) == actual, f"Daily baseline reported {slug}={counts.get(slug)} but actual={actual}")
        need(counts.get("japan", 0) >= 8, "Daily baseline Japan must be >=8")
        need(coverage.get("deskLatestDepthMet") is True, "Daily baseline requires deskLatestDepthMet=true")
        return

    need(coverage.get("status") == "COMPLETE", f"Hourly Live coverage must be COMPLETE, got {coverage.get('status')!r}")
    need(coverage.get("publishingGateMet") is True, "Hourly Live requires publishingGateMet=true")
    need(coverage.get("deskLatestDepthMet") is True, "Hourly Live requires deskLatestDepthMet=true")
    need(coverage.get("footballGateMet") is True, "Hourly Live requires footballGateMet=true")
    counts = coverage.get("deskLatestStoryCounts")
    need(isinstance(counts, dict), "Hourly Live requires deskLatestStoryCounts")
    for slug, minimum in DEPTH_FLOOR.items():
        actual_count = len(desk.get("desks", {}).get(slug, []))
        need(actual_count >= minimum, f"Hourly Live desk {slug} depth {actual_count} < {minimum}")
        need(counts.get(slug) == actual_count, f"Hourly Live reported {slug}={counts.get(slug)} but actual={actual_count}")

    need(items, "Hourly Live publication must never be empty")
    actual = {"NEW": 0, "UPDATED": 0, "DEVELOPING": 0}
    ids = []
    for index, story in enumerate(items):
        rich_story(story, f"live[{index}]")
        status = story.get("status")
        need(status in actual, f"live[{index}] invalid status {status!r}")
        actual[status] += 1
        ids.append(story["id"])
    need(len(ids) == len(set(ids)), "Live has duplicate story ids")

    new_count = live.get("newCount")
    updated_count = live.get("updatedCount")
    developing_count = live.get("developingCount")
    need(isinstance(new_count, int) and new_count >= 0, "Live newCount must be a non-negative integer")
    need(isinstance(updated_count, int) and updated_count >= 0, "Live updatedCount must be a non-negative integer")
    need(isinstance(developing_count, int) and developing_count >= 0, "Live developingCount must be a non-negative integer")
    need(new_count + updated_count == len(items), "Live newCount + updatedCount must equal item count")
    need(new_count >= actual["NEW"], "Live newCount cannot be lower than NEW-status stories")
    need(updated_count >= actual["UPDATED"], "Live updatedCount cannot be lower than UPDATED-status stories")
    need(developing_count == actual["DEVELOPING"], "Live developingCount mismatch")


def validate_desks(desk):
    need(desk.get("mode") == "ROLLING_DESK_LATEST", "desk-latest mode invalid")
    desks = desk.get("desks")
    need(isinstance(desks, dict), "desk-latest desks must be an object")
    for slug, minimum in DEPTH_FLOOR.items():
        stories = desks.get(slug)
        need(isinstance(stories, list), f"desk {slug} must be an array")
        need(len(stories) >= minimum, f"desk {slug} depth {len(stories)} < {minimum}")
        age = newest_age_hours(stories)
        max_age = PUBLIC_DESK_FRESHNESS_HOURS[slug]
        need(age is not None and age <= max_age, f"desk {slug} stale: newest age={age!r}h > {max_age}h")
        seen = set()
        previous = None
        for index, story in enumerate(stories):
            rich_story(story, f"desk {slug}[{index}]")
            need(story["id"] not in seen, f"desk {slug} duplicate id {story['id']}")
            seen.add(story["id"])
            slugs = story.get("deskSlugs")
            need(isinstance(slugs, list) and slug in slugs, f"desk {slug}[{index}] deskSlugs mismatch")
            resolved = routed_slugs(story)
            need(slug in resolved, f"desk {slug}[{index}] hard-routing mismatch: {story['id']} -> {resolved}")
            stamp = editorial_story_time(story)
            need(stamp is not None, f"desk {slug}[{index}] has no resolvable editorial timestamp")
            if previous is not None:
                need(previous >= stamp, f"desk {slug} not newest-first at index {index}: {story['id']}")
            previous = stamp
    need(len(desks.get("japan", [])) >= 8, "Japan desk must contain at least 8 unique current stories")


def report_voice_currentness_nonblocking():
    """Surface voice health without delaying text publication."""
    validator = ROOT / "scripts" / "validate_voice_currentness.py"
    if not validator.exists():
        print("VOICE_CURRENTNESS_AUDIT_MISSING", file=sys.stderr)
        return
    proc = subprocess.run(
        [sys.executable, str(validator)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        if proc.stderr.strip():
            print(proc.stderr.strip(), file=sys.stderr)
        print(
            "VOICE_CURRENTNESS_PENDING_NONBLOCKING publication may deploy; COMPLETE must wait for self-healing audio closure",
            file=sys.stderr,
        )
    else:
        print("VOICE_CURRENTNESS_OK")


def main():
    latest = load("latest.json")
    live = load("live.json")
    desk = load("desk-latest.json")
    validate_desks(desk)
    validate_live(latest, live, desk)
    print("CURRENT_PUBLICATION_TEXT_VALIDATION_OK", live["windowLabel"], f"mode={live['mode']}", f"items={len(live['items'])}", f"japan={len(desk['desks']['japan'])}", f"next={live['nextUpdateLabel']}")
    report_voice_currentness_nonblocking()


if __name__ == "__main__":
    main()
