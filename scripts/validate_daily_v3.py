#!/usr/bin/env python3
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
REQUIRED = ("title", "dek", "summary", "body", "context", "why", "watchNext", "sourceName", "sourceUrl", "timeLabel")
PROCESS_PATTERNS = [
    r"今日未找到", r"採全產業掃描", r"本輪", r"本報", r"incremental", r"duplicate",
    r"重複刊登", r"coverage (?:check|test)", r"collection (?:design|test)", r"這次重新檢查",
    r"之後每一輪", r"每一輪Football", r"不應由全球搜尋排名決定"
]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message):
    raise ValueError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def measure(text):
    cjk = len(re.findall(r"[\u3400-\u9fff]", str(text or "")))
    return cjk if cjk >= 50 else len(re.sub(r"\s+", "", str(text or "")))


def validate_story(story, label):
    if not isinstance(story, dict):
        fail(f"{label}: story must be object")
    if not nonempty(story.get("id")):
        fail(f"{label}: id required")
    for field in REQUIRED:
        if not nonempty(story.get(field)):
            fail(f"{label}: missing {field}")
    body = story["body"]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paragraphs) < 2:
        fail(f"{label}: body needs >=2 paragraphs")
    length = measure(body)
    if length < 100:
        fail(f"{label}: body too short ({length}; need >=100)")
    if length > 1800:
        fail(f"{label}: body too long ({length})")
    combined = " ".join(str(story.get(k, "")) for k in ("title","dek","summary","body","context","why","watchNext"))
    for pattern in PROCESS_PATTERNS:
        if re.search(pattern, combined, flags=re.I):
            fail(f"{label}: public copy contains editorial/process text ({pattern})")
    sources = story.get("sources")
    if sources is not None:
        if not isinstance(sources, list) or not sources:
            fail(f"{label}: sources must be non-empty array when present")
        for i, source in enumerate(sources):
            if not isinstance(source, dict) or not nonempty(source.get("name")) or not nonempty(source.get("url")):
                fail(f"{label}: invalid sources[{i}]")


def validate_sections(data, label):
    articles = data.get("articles")
    if not isinstance(articles, list):
        fail(f"{label}: articles must be array")
    ids = [a.get("id") for a in articles if isinstance(a, dict)]
    if len(ids) != len(articles) or len(ids) != len(set(ids)):
        fail(f"{label}: invalid or duplicate article ids")
    known = set(ids)
    sections = data.get("sections")
    if not isinstance(sections, list):
        fail(f"{label}: sections must be array")
    for section in sections:
        if not isinstance(section, dict):
            fail(f"{label}: section entries must be objects")
        for article_id in section.get("articleIds", []):
            if article_id not in known:
                fail(f"{label}: section {section.get('slug')} references unknown {article_id}")

    world = next((s for s in sections if s.get("slug") == "world"), None)
    asia = next((s for s in sections if s.get("slug") == "asia"), None)
    if world:
        subtitle = str(world.get("subtitle", ""))
        if "中東" in subtitle or "Middle East" in subtitle or "西亞" in subtitle:
            fail(f"{label}: World subtitle must exclude Asia/West Asia/Middle East")
        for article_id in world.get("articleIds", []):
            story = next((a for a in articles if a.get("id") == article_id), {})
            section_name = str(story.get("section", ""))
            if re.search(r"西亞|中東|伊朗|以色列|海灣|Middle East|West Asia", section_name, flags=re.I):
                fail(f"{label}: Asian story {article_id} cannot be in World")
    if asia:
        subtitle = str(asia.get("subtitle", ""))
        required_terms = ("東亞", "東南亞", "南亞", "中亞")
        if not all(term in subtitle for term in required_terms) or not ("西亞" in subtitle or "中東" in subtitle):
            fail(f"{label}: Asia subtitle must represent Whole Asia")


def validate_file(path, label, require_top=False):
    data = load(path)
    if int(data.get("contentVersion", 1) or 1) < 3:
        return
    if int(data.get("editorialStandardVersion", 1) or 1) < 3:
        fail(f"{label}: v3 content requires editorialStandardVersion>=3")
    validate_sections(data, label)
    for i, story in enumerate(data.get("articles", [])):
        validate_story(story, f"{label}: articles[{i}]")
    if require_top:
        known = {a.get("id") for a in data.get("articles", [])}
        if data.get("leadId") not in known:
            fail(f"{label}: leadId invalid")
        top = data.get("topFive")
        if not isinstance(top, list) or not all(i in known for i in top):
            fail(f"{label}: topFive invalid")


def main():
    try:
        latest = DATA / "latest.json"
        validate_file(latest, "data/latest.json", require_top=True)
        data = load(latest)
        date = data.get("date")
        if date:
            dated = DATA / f"{date}.json"
            if dated.exists():
                validate_file(dated, f"data/{date}.json", require_top=True)
            topic = DATA / "topic-more" / f"{date}.json"
            if topic.exists():
                validate_file(topic, f"data/topic-more/{date}.json", require_top=False)
        print("DAILY V3 VALIDATION OK")
        return 0
    except Exception as exc:
        print("DAILY V3 VALIDATION FAILED", file=sys.stderr)
        print(f"- {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
