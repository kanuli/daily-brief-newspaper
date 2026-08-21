#!/usr/bin/env python3
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def load_json(path: pathlib.Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"{path.relative_to(ROOT)}: invalid JSON: {exc}") from exc


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_edition(data, label, require_sections=True):
    require(isinstance(data, dict), f"{label}: root must be an object")
    articles = data.get("articles")
    require(isinstance(articles, list) and articles, f"{label}: articles must be a non-empty array")

    ids = [a.get("id") for a in articles if isinstance(a, dict)]
    require(len(ids) == len(articles), f"{label}: every article must be an object with id")
    require(all(isinstance(i, str) and i for i in ids), f"{label}: every article id must be a non-empty string")
    require(len(ids) == len(set(ids)), f"{label}: duplicate article ids")
    known = set(ids)

    lead = data.get("leadId")
    require(lead in known, f"{label}: leadId does not resolve to an article")

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
        require(isinstance(slug, str) and slug, f"{label}: section.slug must be a non-empty string")
        require(isinstance(title, str) and title, f"{label}: {slug}.title must be a non-empty string")
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
        title = section.get("title")
        subtitle = section.get("subtitle")
        article_ids = section.get("articleIds")
        require(isinstance(slug, str) and slug, f"{label}: section.slug must be a non-empty string")
        require(isinstance(title, str) and title, f"{label}: {slug}.title must be a non-empty string")
        require(isinstance(subtitle, str), f"{label}: {slug}.subtitle must be a string")
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


def validate_live(data, label):
    require(isinstance(data, dict), f"{label}: root must be an object")
    require(isinstance(data.get("items", []), list), f"{label}: items must be an array")
    require(isinstance(data.get("nextUpdateLabel"), str) and data.get("nextUpdateLabel"), f"{label}: nextUpdateLabel is required")

    for item in data.get("items", []):
        require(isinstance(item, dict), f"{label}: every item must be an object")
        require(item.get("status") in {"NEW", "UPDATED", "DEVELOPING"}, f"{label}: invalid Live status {item.get('status')!r}")
        require(isinstance(item.get("id"), str) and item.get("id"), f"{label}: every item needs id")
        require(isinstance(item.get("title"), str) and item.get("title"), f"{label}: every item needs title")

    coverage = data.get("coverage")
    require(isinstance(coverage, dict), f"{label}: coverage must be an object")
    status = str(coverage.get("status", "")).upper()
    require(status, f"{label}: coverage.status is required")

    # Daily reset and one-time schedule migration are allowed to omit an hourly search audit.
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

    require(isinstance(coverage["checkedDesks"], list) and len(coverage["checkedDesks"]) == 9,
            f"{label}: checkedDesks must contain all 9 desks")
    require(isinstance(coverage["sourceOrganizationsChecked"], list),
            f"{label}: sourceOrganizationsChecked must be an array")
    require(isinstance(coverage["sourceOrganizationCount"], int),
            f"{label}: sourceOrganizationCount must be an integer")
    require(isinstance(coverage["freshSearchCount"], int),
            f"{label}: freshSearchCount must be an integer")
    require(isinstance(coverage["rawFreshCandidateCount"], int),
            f"{label}: rawFreshCandidateCount must be an integer")
    require(isinstance(coverage["verifiedCandidateCount"], int),
            f"{label}: verifiedCandidateCount must be an integer")
    require(isinstance(coverage["incrementalCandidateCount"], int),
            f"{label}: incrementalCandidateCount must be an integer")
    require(isinstance(coverage["publishedCount"], int),
            f"{label}: publishedCount must be an integer")
    require(isinstance(coverage["countryVerification"], list),
            f"{label}: countryVerification must be an array")

    if status == "COMPLETE":
        require(coverage["sourceOrganizationCount"] >= 30,
                f"{label}: COMPLETE hourly run needs at least 30 organizations")
        require(coverage["freshSearchCount"] >= 24,
                f"{label}: COMPLETE hourly run needs at least 24 fresh searches")
        require(coverage["deskMinimumsMet"] is True,
                f"{label}: COMPLETE hourly run requires deskMinimumsMet=true")
        require(coverage["rawFreshCandidateCount"] > 0,
                f"{label}: rawFreshCandidateCount=0 cannot be COMPLETE; use COLLECTION_FAILURE/INCOMPLETE")

    if coverage["rawFreshCandidateCount"] == 0:
        require(status in {"COLLECTION_FAILURE", "INCOMPLETE"},
                f"{label}: zero raw fresh candidates must be COLLECTION_FAILURE/INCOMPLETE")


def main():
    errors = []
    try:
        latest = load_json(DATA / "latest.json")
        validate_edition(latest, "data/latest.json", require_sections=True)
        date = latest.get("date")
        require(isinstance(date, str) and date, "data/latest.json: date is required")

        dated_path = DATA / f"{date}.json"
        if dated_path.exists():
            validate_edition(load_json(dated_path), str(dated_path.relative_to(ROOT)), require_sections=True)

        topic_path = DATA / "topic-more" / f"{date}.json"
        if topic_path.exists():
            validate_topic_more(load_json(topic_path), latest, str(topic_path.relative_to(ROOT)))

        vocab_path = DATA / "vocab" / f"{date}.json"
        if vocab_path.exists():
            validate_vocab(load_json(vocab_path), str(vocab_path.relative_to(ROOT)))

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
