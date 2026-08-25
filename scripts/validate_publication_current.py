#!/usr/bin/env python3
import json
import pathlib
import re

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
MIN_BODY_MEASURE = 60


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
    measure = cjk if cjk >= 30 else len(re.sub(r"\s+", "", story["body"]))
    need(measure >= MIN_BODY_MEASURE, f"{label}: body too short ({measure})")


def validate_live(latest, live):
    need(str(live.get("mode") or "").upper() == "LIVE", "live mode invalid")
    need(live.get("date") == latest.get("date"), "live date does not match Daily date")
    for key in ("lastUpdated", "lastUpdatedLabel", "windowLabel", "nextUpdateLabel"):
        need(isinstance(live.get(key), str) and live[key].strip(), f"live missing {key}")
    items = live.get("items")
    need(isinstance(items, list) and items, "Live publication must never be empty")
    actual = {"NEW": 0, "UPDATED": 0, "DEVELOPING": 0}
    ids = []
    for index, story in enumerate(items):
        rich_story(story, f"live[{index}]")
        status = story.get("status")
        need(status in actual, f"live[{index}] invalid status {status!r}")
        actual[status] += 1
        ids.append(story["id"])
    need(len(ids) == len(set(ids)), "Live has duplicate story ids")
    need(live.get("newCount") == actual["NEW"], "Live newCount mismatch")
    need(live.get("updatedCount") == actual["UPDATED"], "Live updatedCount mismatch")
    need(live.get("developingCount") == actual["DEVELOPING"], "Live developingCount mismatch")
    coverage = live.get("coverage")
    need(isinstance(coverage, dict) and str(coverage.get("status", "")).strip(), "Live coverage.status required")


def validate_desks(desk):
    need(desk.get("mode") == "ROLLING_DESK_LATEST", "desk-latest mode invalid")
    desks = desk.get("desks")
    need(isinstance(desks, dict), "desk-latest desks must be an object")
    for slug in EXPECTED_DESKS:
        stories = desks.get(slug)
        need(isinstance(stories, list) and stories, f"desk {slug} must not be empty")
        seen = set()
        for index, story in enumerate(stories):
            rich_story(story, f"desk {slug}[{index}]")
            need(story["id"] not in seen, f"desk {slug} duplicate id {story['id']}")
            seen.add(story["id"])
            slugs = story.get("deskSlugs")
            need(isinstance(slugs, list) and slug in slugs, f"desk {slug}[{index}] deskSlugs mismatch")


def main():
    latest = load("latest.json")
    live = load("live.json")
    desk = load("desk-latest.json")
    validate_live(latest, live)
    validate_desks(desk)
    print(
        "CURRENT_PUBLICATION_VALIDATION_OK",
        live["windowLabel"],
        f"items={len(live['items'])}",
        f"next={live['nextUpdateLabel']}",
    )


if __name__ == "__main__":
    main()
