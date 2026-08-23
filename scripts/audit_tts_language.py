#!/usr/bin/env python3
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import generate_cosyvoice_all as gen
import tts_hktrad

FIELDS = ("title", "dek", "summary", "body", "context", "background", "why", "whyImportant", "watchNext", "nextStep")
DESK_ORDER = ["world", "asia", "hong-kong", "japan", "finance", "stock-news", "ai-tech", "manga-anime", "manchester-united", "football"]


def desk_for(story):
    desk = str(story.get("desk") or "").strip()
    if desk:
        return desk
    slugs = story.get("deskSlugs") or []
    if isinstance(slugs, list) and slugs:
        return str(slugs[0])
    return "unknown"


def speech_text(story):
    values=[]; seen=set()
    for key in FIELDS:
        value=gen.clean(story.get(key))
        if value and value not in seen:
            seen.add(value); values.append(value)
    return "\n".join(values)


def main():
    latest, _ = gen.load_json(Path("data/latest.json"))
    date_value = (latest or {}).get("date")
    by_title = {}
    for path in gen.source_paths(date_value):
        data, _ = gen.load_json(path)
        if data is None:
            continue
        for story in gen.walk_stories(data):
            title = gen.clean(story.get("title"))
            if not title:
                continue
            old = by_title.get(title)
            if old is None or len(speech_text(story)) > len(speech_text(old)):
                by_title[title] = story

    grouped = defaultdict(list)
    token_counts = defaultdict(lambda: defaultdict(int))
    clean_count = defaultdict(int)
    total_count = defaultdict(int)
    for title, story in by_title.items():
        desk = desk_for(story)
        total_count[desk] += 1
        source = speech_text(story)
        localized = tts_hktrad.localize(source)
        tokens = tts_hktrad.residual_latin_tokens(localized)
        if not tokens:
            clean_count[desk] += 1
            continue
        grouped[desk].append({
            "id": gen.story_identity(story),
            "title": title,
            "tokens": tokens,
        })
        for token in tokens:
            token_counts[desk][token] += 1

    desks = {}
    for desk in DESK_ORDER + sorted(set(total_count) - set(DESK_ORDER)):
        if desk not in total_count:
            continue
        unresolved = grouped.get(desk, [])
        desks[desk] = {
            "storyCount": total_count[desk],
            "cleanStoryCount": clean_count[desk],
            "unresolvedStoryCount": len(unresolved),
            "coverageComplete": len(unresolved) == 0,
            "topResidualTokens": [
                {"token": token, "storyCount": count}
                for token, count in sorted(token_counts[desk].items(), key=lambda x: (-x[1], x[0].lower()))[:50]
            ],
            "stories": unresolved,
        }

    report = {
        "version": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "date": date_value,
        "policy": "hk-traditional-chinese-first; taiwan-traditional-fallback",
        "deskPriority": DESK_ORDER,
        "storyCount": sum(total_count.values()),
        "cleanStoryCount": sum(clean_count.values()),
        "unresolvedStoryCount": sum(len(v) for v in grouped.values()),
        "desks": desks,
    }
    out = Path("/tmp/tts-language-audit.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        "storyCount": report["storyCount"],
        "cleanStoryCount": report["cleanStoryCount"],
        "unresolvedStoryCount": report["unresolvedStoryCount"],
        "deskSummary": {k: {"clean": v["cleanStoryCount"], "total": v["storyCount"], "unresolved": v["unresolvedStoryCount"]} for k,v in desks.items()},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
