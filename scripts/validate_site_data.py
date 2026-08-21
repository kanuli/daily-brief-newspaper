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
        article_ids = section.get("articleIds")
        require(isinstance(slug, str) and slug, f"{label}: section.slug must be a non-empty string")
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
    for section in sections:
        slug = section.get("slug")
        article_ids = section.get("articleIds")
        require(isinstance(slug, str) and slug, f"{label}: section.slug must be a non-empty string")
        require(isinstance(article_ids, list), f"{label}: {slug}.articleIds must be an array")
        require(all(i in known for i in article_ids), f"{label}: {slug} contains unknown article ids")


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


def main():
    errors = []
    try:
        latest = load_json(DATA / "latest.json")
        validate_edition(latest, "data/latest.json", require_sections=True)
        date = latest.get("date")
        require(isinstance(date, str) and date, "data/latest.json: date is required")

        dated_path = DATA / f"{date}.json"
        if dated_path.exists():
            # Historical files remain readable because the renderer can reconstruct missing sections.
            # New Daily generations are required by automation QA to emit full section objects.
            validate_edition(load_json(dated_path), str(dated_path.relative_to(ROOT)), require_sections=False)

        topic_path = DATA / "topic-more" / f"{date}.json"
        if topic_path.exists():
            validate_topic_more(load_json(topic_path), latest, str(topic_path.relative_to(ROOT)))

        vocab_path = DATA / "vocab" / f"{date}.json"
        if vocab_path.exists():
            validate_vocab(load_json(vocab_path), str(vocab_path.relative_to(ROOT)))

        live_path = DATA / "live.json"
        if live_path.exists():
            live = load_json(live_path)
            require(isinstance(live.get("items", []), list), "data/live.json: items must be an array")

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
