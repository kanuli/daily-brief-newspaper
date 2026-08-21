#!/usr/bin/env python3
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXPECTED_DESKS = {
    "世界", "亞洲", "香港", "日本", "財經 / 全球市場",
    "AI / 科技", "漫畫 / Anime", "Manchester United", "Football",
}
EXPECTED_DESK_SLUGS = {
    "world", "asia", "hong-kong", "japan", "market-economy",
    "ai-tech", "manga-anime", "manchester-united", "football",
}
RICH_FIELDS = ("title", "dek", "summary", "context", "why", "watchNext")
COMPLETE_SOURCE_MINIMA = {
    "world": 12, "asia": 10, "hong-kong": 8, "japan": 8,
    "market-economy": 10, "ai-tech": 10, "manga-anime": 4,
    "manchester-united": 4, "football": 10,
}


def load_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: invalid JSON: {exc}") from exc


def require(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty_text(value):
    return isinstance(value, str) and bool(value.strip())


def validate_rich_story(story, label):
    require(isinstance(story, dict), f"{label}: story must be an object")
    require(nonempty_text(story.get("id")), f"{label}: id is required")
    for field in RICH_FIELDS:
        require(nonempty_text(story.get(field)), f"{label}: {field} is required for newspaper-depth rendering")
    require(nonempty_text(story.get("section")), f"{label}: section is required")
    require(nonempty_text(story.get("sourceName")), f"{label}: sourceName is required")
    require(nonempty_text(story.get("sourceUrl")), f"{label}: sourceUrl is required")
    require(nonempty_text(story.get("timeLabel")), f"{label}: timeLabel is required")
    sources = story.get("sources")
    if sources is not None:
        require(isinstance(sources, list), f"{label}: sources must be an array when present")
        for index, source in enumerate(sources):
            require(isinstance(source, dict), f"{label}: sources[{index}] must be an object")
            require(nonempty_text(source.get("name")), f"{label}: sources[{index}].name is required")
            require(nonempty_text(source.get("url")), f"{label}: sources[{index}].url is required")


def validate_edition(data, label, require_sections=True):
    require(isinstance(data, dict), f"{label}: root must be an object")
    articles = data.get("articles")
    require(isinstance(articles, list) and articles, f"{label}: articles must be a non-empty array")
    ids = [a.get("id") for a in articles if isinstance(a, dict)]
    require(len(ids) == len(articles), f"{label}: every article must be an object with id")
    require(all(nonempty_text(i) for i in ids), f"{label}: every article id must be a non-empty string")
    require(len(ids) == len(set(ids)), f"{label}: duplicate article ids")
    known = set(ids)
    require(data.get("leadId") in known, f"{label}: leadId does not resolve to an article")
    top = data.get("topFive")
    require(isinstance(top, list), f"{label}: topFive must be an array")
    require(all(i in known for i in top), f"{label}: topFive contains unknown article ids")
    sections = data.get("sections")
    if not require_sections and sections is None:
        return
    require(isinstance(sections, list) and sections, f"{label}: sections must be a non-empty array")
    require(all(isinstance(s, dict) for s in sections), f"{label}: sections entries must be objects, never strings")
    slugs = []
    for section in sections:
        slug = section.get("slug")
        title = section.get("title")
        subtitle = section.get("subtitle")
        article_ids = section.get("articleIds")
        require(nonempty_text(slug), f"{label}: section.slug must be a non-empty string")
        require(nonempty_text(title), f"{label}: {slug}.title must be a non-empty string")
        require(isinstance(subtitle, str), f"{label}: {slug}.subtitle must be a string")
        require(isinstance(article_ids, list), f"{label}: {slug}.articleIds must be an array")
        require(all(i in known for i in article_ids), f"{label}: {slug} contains unknown article ids")
        slugs.append(slug)
    require(len(slugs) == len(set(slugs)), f"{label}: duplicate section slugs")


def validate_topic_more(data, latest, label):
    require(isinstance(data, dict), f"{label}: root must be an object")
    articles = data.get("articles", [])
    require(isinstance(articles, list), f"{label}: articles must be an array")
    extra_ids = {a.get("id") for a in articles if isinstance(a, dict) and a.get("id")}
    latest_ids = {a.get("id") for a in latest.get("articles", []) if isinstance(a, dict) and a.get("id")}
    known = extra_ids | latest_ids
    sections = data.get("sections")
    require(isinstance(sections, list), f"{label}: sections must be an array")
    require(all(isinstance(s, dict) for s in sections), f"{label}: sections entries must be objects, never strings")
    slugs = []
    for section in sections:
        slug = section.get("slug")
        require(nonempty_text(slug), f"{label}: section.slug must be a non-empty string")
        require(nonempty_text(section.get("title")), f"{label}: {slug}.title must be a non-empty string")
        require(isinstance(section.get("subtitle"), str), f"{label}: {slug}.subtitle must be a string")
        article_ids = section.get("articleIds")
        require(isinstance(article_ids, list), f"{label}: {slug}.articleIds must be an array")
        require(all(i in known for i in article_ids), f"{label}: {slug} contains unknown article ids")
        slugs.append(slug)
    require(len(slugs) == len(set(slugs)), f"{label}: duplicate section slugs")


def validate_vocab(data, label):
    words = data.get("words") if isinstance(data, dict) else None
    require(isinstance(words, list) and len(words) == 10, f"{label}: words must contain exactly 10 entries")
    counts = {level: 0 for level in ("N1", "N2", "N3", "N4", "N5")}
    for word in words:
        require(isinstance(word, dict), f"{label}: each word must be an object")
        level = word.get("level")
        require(level in counts, f"{label}: invalid JLPT level {level!r}")
        require(word.get("reading"), f"{label}: every word needs reading")
        counts[level] += 1
    require(all(count == 2 for count in counts.values()), f"{label}: each of N1-N5 must contain exactly 2 words: {counts}")


def validate_desk_latest(data, label):
    require(isinstance(data, dict), f"{label}: root must be an object")
    require(data.get("mode") == "ROLLING_DESK_LATEST", f"{label}: mode must be ROLLING_DESK_LATEST")
    require(nonempty_text(data.get("generatedAt")), f"{label}: generatedAt is required")
    desks = data.get("desks")
    require(isinstance(desks, dict), f"{label}: desks must be an object")
    missing = EXPECTED_DESK_SLUGS - set(desks)
    require(not missing, f"{label}: missing desk keys: {sorted(missing)}")

    for slug in sorted(EXPECTED_DESK_SLUGS):
        stories = desks.get(slug)
        require(isinstance(stories, list), f"{label}: desks.{slug} must be an array")
        require(len(stories) >= 1, f"{label}: desks.{slug} must not be empty")
        ids = []
        for index, story in enumerate(stories):
            validate_rich_story(story, f"{label}: desks.{slug}[{index}]")
            require(story.get("status") in {"LATEST", "NEW", "UPDATED"},
                    f"{label}: desks.{slug}[{index}] invalid status {story.get('status')!r}")
            desk_slugs = story.get("deskSlugs")
            require(isinstance(desk_slugs, list) and desk_slugs,
                    f"{label}: desks.{slug}[{index}].deskSlugs must be a non-empty array")
            require(slug in desk_slugs,
                    f"{label}: desks.{slug}[{index}] must include {slug!r} in deskSlugs")
            ids.append(story["id"])
        require(len(ids) == len(set(ids)), f"{label}: desks.{slug} contains duplicate story ids")

    require(len(desks.get("hong-kong", [])) >= 3,
            f"{label}: Hong Kong Desk must contain at least 3 current verified newspaper stories")
    require(len(desks.get("japan", [])) >= 3,
            f"{label}: Japan Desk must contain at least 3 current verified newspaper stories")


def validate_live(data, label):
    require(isinstance(data, dict), f"{label}: root must be an object")
    items = data.get("items", [])
    require(isinstance(items, list), f"{label}: items must be an array")
    require(nonempty_text(data.get("nextUpdateLabel")), f"{label}: nextUpdateLabel is required")

    item_ids = []
    actual = {"NEW": 0, "UPDATED": 0, "DEVELOPING": 0}
    for index, item in enumerate(items):
        validate_rich_story(item, f"{label}: items[{index}]")
        status_value = item.get("status")
        require(status_value in actual, f"{label}: invalid Live status {status_value!r}")
        item_ids.append(item["id"])
        actual[status_value] += 1
    require(len(item_ids) == len(set(item_ids)), f"{label}: duplicate Live item ids")

    require(data.get("newCount") == actual["NEW"],
            f"{label}: newCount={data.get('newCount')} but actual NEW items={actual['NEW']}")
    require(data.get("updatedCount") == actual["UPDATED"],
            f"{label}: updatedCount={data.get('updatedCount')} but actual UPDATED items={actual['UPDATED']}")
    require(data.get("developingCount") == actual["DEVELOPING"],
            f"{label}: developingCount={data.get('developingCount')} but actual DEVELOPING items={actual['DEVELOPING']}")

    coverage = data.get("coverage")
    require(isinstance(coverage, dict), f"{label}: coverage must be an object")
    status = str(coverage.get("status", "")).upper()
    require(status, f"{label}: coverage.status is required")
    if status in {"DAILY_BASELINE", "SCHEDULE_MIGRATION"}:
        return

    required = [
        "scheduledSlot", "scheduledWindowStart", "windowStart", "baselineAt", "checkedAt",
        "checkedDesks", "sourceOrganizationsChecked", "sourceOrganizationCount", "freshSearchCount",
        "firstPassRawFreshCandidateCount", "secondPassTriggered", "secondPassSearchCount",
        "recoveryPassTriggered", "rawFreshCandidateCount", "verifiedCandidateCount",
        "incrementalCandidateCount", "duplicatesAlreadyInDaily", "rejectedDuplicates",
        "publishedCount", "countryVerification", "deskMinimumsMet", "qaNote",
    ]
    missing = [key for key in required if key not in coverage]
    require(not missing, f"{label}: hourly coverage missing fields: {missing}")

    desks = coverage["checkedDesks"]
    require(isinstance(desks, list), f"{label}: checkedDesks must be an array")
    require(set(desks) == EXPECTED_DESKS and len(desks) == len(EXPECTED_DESKS),
            f"{label}: checkedDesks must contain exactly the 9 required desks")

    sources = coverage["sourceOrganizationsChecked"]
    require(isinstance(sources, list), f"{label}: sourceOrganizationsChecked must be an array")
    require(all(nonempty_text(s) for s in sources), f"{label}: every source organization must be a non-empty string")
    unique_sources = {s.strip().casefold() for s in sources}
    require(len(unique_sources) == len(sources), f"{label}: sourceOrganizationsChecked contains duplicates")

    int_fields = [
        "sourceOrganizationCount", "freshSearchCount", "firstPassRawFreshCandidateCount",
        "secondPassSearchCount", "rawFreshCandidateCount", "verifiedCandidateCount",
        "incrementalCandidateCount", "duplicatesAlreadyInDaily", "rejectedDuplicates", "publishedCount",
    ]
    for field in int_fields:
        require(isinstance(coverage[field], int) and coverage[field] >= 0, f"{label}: {field} must be a non-negative integer")
    require(coverage["sourceOrganizationCount"] == len(unique_sources),
            f"{label}: sourceOrganizationCount must equal the unique source list length")
    require(isinstance(coverage["secondPassTriggered"], bool), f"{label}: secondPassTriggered must be boolean")
    require(isinstance(coverage["recoveryPassTriggered"], bool), f"{label}: recoveryPassTriggered must be boolean")
    require(isinstance(coverage["countryVerification"], list), f"{label}: countryVerification must be an array")
    require(coverage["verifiedCandidateCount"] <= coverage["rawFreshCandidateCount"],
            f"{label}: verified candidates cannot exceed raw fresh candidates")
    require(coverage["incrementalCandidateCount"] <= coverage["verifiedCandidateCount"],
            f"{label}: incremental candidates cannot exceed verified candidates")
    require(coverage["publishedCount"] <= coverage["incrementalCandidateCount"],
            f"{label}: publishedCount cannot exceed incrementalCandidateCount")

    if coverage["firstPassRawFreshCandidateCount"] <= 3:
        require(coverage["secondPassTriggered"] is True,
                f"{label}: first-pass raw <=3 requires second pass")
        require(coverage["secondPassSearchCount"] >= 12,
                f"{label}: required second pass needs at least 12 additional searches")

    if coverage["rawFreshCandidateCount"] == 0:
        require(status in {"COLLECTION_FAILURE", "INCOMPLETE"},
                f"{label}: zero raw fresh candidates must be COLLECTION_FAILURE/INCOMPLETE")
        require(coverage["recoveryPassTriggered"] is True,
                f"{label}: zero final raw fresh candidates require recovery pass")

    if status == "COMPLETE":
        for field in ("deskCandidateCounts", "deskSourceCounts", "deskSearchCounts", "deskRecoveryTriggered"):
            require(isinstance(coverage.get(field), dict), f"{label}: COMPLETE run requires coverage.{field}")
        require(coverage["sourceOrganizationCount"] >= 40,
                f"{label}: COMPLETE hourly run needs at least 40 unique organizations")
        require(coverage["freshSearchCount"] >= 36,
                f"{label}: COMPLETE hourly run needs at least 36 fresh/source-specific checks")
        require(coverage["deskMinimumsMet"] is True,
                f"{label}: COMPLETE hourly run requires deskMinimumsMet=true")
        require(coverage["rawFreshCandidateCount"] > 0,
                f"{label}: rawFreshCandidateCount=0 cannot be COMPLETE")

        candidate_counts = coverage["deskCandidateCounts"]
        source_counts = coverage["deskSourceCounts"]
        search_counts = coverage["deskSearchCounts"]
        recovery_flags = coverage["deskRecoveryTriggered"]
        for slug in EXPECTED_DESK_SLUGS:
            require(isinstance(candidate_counts.get(slug), int) and candidate_counts.get(slug) >= 0,
                    f"{label}: COMPLETE run requires non-negative {slug} candidate count")
            require(isinstance(source_counts.get(slug), int) and source_counts.get(slug) >= COMPLETE_SOURCE_MINIMA[slug],
                    f"{label}: COMPLETE run has insufficient {slug} source coverage: {source_counts.get(slug)}")
            require(isinstance(search_counts.get(slug), int) and search_counts.get(slug) >= 1,
                    f"{label}: COMPLETE run requires at least one recorded search/check for {slug}")
            require(isinstance(recovery_flags.get(slug), bool),
                    f"{label}: COMPLETE run requires boolean deskRecoveryTriggered.{slug}")


def main():
    errors = []
    try:
        latest = load_json(DATA / "latest.json")
        validate_edition(latest, "data/latest.json", require_sections=True)
        date = latest.get("date")
        require(nonempty_text(date), "data/latest.json: date is required")

        dated_path = DATA / f"{date}.json"
        if dated_path.exists():
            validate_edition(load_json(dated_path), str(dated_path.relative_to(ROOT)), require_sections=False)

        topic_path = DATA / "topic-more" / f"{date}.json"
        if topic_path.exists():
            validate_topic_more(load_json(topic_path), latest, str(topic_path.relative_to(ROOT)))

        vocab_path = DATA / "vocab" / f"{date}.json"
        if vocab_path.exists():
            validate_vocab(load_json(vocab_path), str(vocab_path.relative_to(ROOT)))

        desk_path = DATA / "desk-latest.json"
        require(desk_path.exists(), "data/desk-latest.json is required for rolling newspaper mode")
        validate_desk_latest(load_json(desk_path), "data/desk-latest.json")

        live_path = DATA / "live.json"
        if live_path.exists():
            validate_live(load_json(live_path), "data/live.json")
    except Exception as exc:
        errors.append(str(exc))

    if errors:
        print("SITE DATA VALIDATION FAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("SITE DATA VALIDATION OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
