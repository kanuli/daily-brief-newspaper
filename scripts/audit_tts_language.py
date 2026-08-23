#!/usr/bin/env python3
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import tts_hktrad as base_hktrad
import tts_hktrad_v2 as tts_hktrad

FIELDS = ("title", "dek", "summary", "body", "context", "background", "why", "whyImportant", "watchNext", "nextStep")
DESK_ORDER = ["world", "asia", "hong-kong", "japan", "finance", "stock-news", "ai-tech", "manga-anime", "manchester-united", "football"]
_DIGITS = "零一二三四五六七八九"


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def safe_id(value):
    raw = clean(value).lower()
    raw = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-._")
    return raw[:72] or "story-" + hashlib.sha256(clean(value).encode("utf-8")).hexdigest()[:16]


def story_identity(story):
    return safe_id(story.get("id") or story.get("articleId") or story.get("storyId") or story.get("title"))


def looks_like_story(obj):
    if not isinstance(obj, dict) or not clean(obj.get("title")):
        return False
    return any(clean(obj.get(key)) for key in FIELDS[1:])


def walk_stories(node):
    if isinstance(node, dict):
        if looks_like_story(node):
            yield node
        for value in node.values():
            yield from walk_stories(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_stories(value)


def load_json(path):
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def source_paths(date_value):
    paths = [Path("data/latest.json"), Path("data/desk-latest.json"), Path("data/live.json"), Path("data/stocks-latest.json")]
    if date_value:
        paths.extend([Path(f"data/topic-more/{date_value}.json"), Path(f"data/editorial-overrides/{date_value}.json")])
    return paths


def desk_for(story):
    desk = clean(story.get("desk"))
    if desk:
        return desk
    slugs = story.get("deskSlugs") or []
    if isinstance(slugs, list) and slugs:
        return str(slugs[0])
    return "unknown"


def speech_text(story):
    values = []
    seen = set()
    for key in FIELDS:
        value = clean(story.get(key))
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return "\n".join(values)


def _small_integer_to_chinese(number):
    number = int(number)
    if number < 10:
        return _DIGITS[number]
    if number < 100:
        tens, ones = divmod(number, 10)
        head = "十" if tens == 1 else f"{_DIGITS[tens]}十"
        return head + (_DIGITS[ones] if ones else "")
    if number < 1000:
        hundreds, remainder = divmod(number, 100)
        out = f"{_DIGITS[hundreds]}百"
        if remainder:
            if remainder < 10:
                out += "零"
            out += _small_integer_to_chinese(remainder)
        return out
    if number < 10000:
        thousands, remainder = divmod(number, 1000)
        out = f"{_DIGITS[thousands]}千"
        if remainder:
            if remainder < 100:
                out += "零"
            out += _small_integer_to_chinese(remainder)
        return out
    return "".join(_DIGITS[int(char)] for char in str(number))


def _number_string_for_speech(raw):
    raw = str(raw)
    if len(raw) == 4 and raw.isdigit() and 1900 <= int(raw) <= 2099:
        return "".join(_DIGITS[int(char)] for char in raw)
    if raw.isdigit() and int(raw) < 10000:
        return _small_integer_to_chinese(int(raw))
    if raw.isdigit():
        return "".join(_DIGITS[int(char)] for char in raw)
    return raw


def _number_for_speech(match):
    raw = match.group(0).replace(",", "")
    if "." in raw:
        whole, fraction = raw.split(".", 1)
        return f"{_number_string_for_speech(whole)}點{''.join(_DIGITS[int(c)] for c in fraction)}"
    return _number_string_for_speech(raw)


def normalize_numbers_for_cantonese(text):
    text = re.sub(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?", _number_for_speech, text)
    text = text.replace("%", "百分比")
    text = text.replace("£", "英鎊").replace("€", "歐元").replace("$", "美元")
    return text


def runtime_localize(text):
    # Lightweight mirror of production normalize_for_tts. Keep this module free
    # of torch/torchaudio so Pages and the audit workflow can run before deploy.
    out = base_hktrad.localize(clean(text))
    out = re.sub(r"[「『“\"]?double[\-‐‑–— ]?tap[」』”\"]?", "二次打擊", out, flags=re.IGNORECASE)
    out = re.sub(r"\bReuters\b", "路透社", out, flags=re.IGNORECASE)
    out = re.sub(r"\bAssociated Press\b", "美聯社", out, flags=re.IGNORECASE)
    out = re.sub(r"\bAP\b", "美聯社", out)
    out = normalize_numbers_for_cantonese(out)
    out = out.replace("–", "，").replace("—", "，")
    return tts_hktrad.localize(clean(out))


def main():
    strict = "--strict" in sys.argv[1:]
    latest = load_json(Path("data/latest.json")) or {}
    date_value = latest.get("date")
    by_title = {}
    for path in source_paths(date_value):
        data = load_json(path)
        if data is None:
            continue
        for story in walk_stories(data):
            title = clean(story.get("title"))
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
        localized = runtime_localize(speech_text(story))
        tokens = tts_hktrad.residual_latin_tokens(localized)
        if not tokens:
            clean_count[desk] += 1
            continue
        grouped[desk].append({"id": story_identity(story), "title": title, "tokens": tokens})
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
        "version": 2,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "date": date_value,
        "policy": "hk-traditional-chinese-first; taiwan-traditional-fallback; runtime-normalization-order",
        "deskPriority": DESK_ORDER,
        "storyCount": sum(total_count.values()),
        "cleanStoryCount": sum(clean_count.values()),
        "unresolvedStoryCount": sum(len(v) for v in grouped.values()),
        "desks": desks,
    }
    out = Path("/tmp/tts-language-audit.json")
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "storyCount": report["storyCount"],
        "cleanStoryCount": report["cleanStoryCount"],
        "unresolvedStoryCount": report["unresolvedStoryCount"],
        "deskSummary": {k: {"clean": v["cleanStoryCount"], "total": v["storyCount"], "unresolved": v["unresolvedStoryCount"]} for k, v in desks.items()},
    }, ensure_ascii=False, indent=2))
    if strict and report["unresolvedStoryCount"]:
        print("HKTRAD_VISIBLE_NEWS_GATE_FAILED", file=sys.stderr)
        for desk, detail in desks.items():
            for story in detail["stories"][:10]:
                print(f"- {desk}: {story['title']} :: {', '.join(story['tokens'])}", file=sys.stderr)
        return 1
    if strict:
        print(f"HKTRAD_VISIBLE_NEWS_GATE_OK {report['cleanStoryCount']}/{report['storyCount']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
