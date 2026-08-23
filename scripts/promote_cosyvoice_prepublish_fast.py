#!/usr/bin/env python3
"""Promote exact-hash prebuilt F01 URLs without importing the TTS runtime.

This handoff intentionally uses only the Python standard library so a successful
prepublish voice can reach the production manifest before the heavy 10-worker
CosyVoice runtime is installed. Missing voices remain pending for normal backfill.
"""
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ("title", "dek", "summary", "body", "context", "background", "why", "whyImportant", "watchNext", "nextStep")
DIGITS = "零一二三四五六七八九"
MANIFEST = Path("data/tts-manifest.json")


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def safe_id(value):
    raw = clean(value).lower()
    raw = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-._")
    return raw[:72] or "story"


def story_identity(story):
    explicit = story.get("id") or story.get("articleId") or story.get("storyId")
    if explicit:
        return safe_id(explicit)
    return "story-" + hashlib.sha256(clean(story.get("title")).encode("utf-8")).hexdigest()[:16]


def small_integer(number):
    number = int(number)
    if number < 10:
        return DIGITS[number]
    if number < 100:
        tens, ones = divmod(number, 10)
        head = "十" if tens == 1 else f"{DIGITS[tens]}十"
        return head + (DIGITS[ones] if ones else "")
    if number < 1000:
        hundreds, remainder = divmod(number, 100)
        out = f"{DIGITS[hundreds]}百"
        if remainder:
            if remainder < 10:
                out += "零"
            out += small_integer(remainder)
        return out
    if number < 10000:
        thousands, remainder = divmod(number, 1000)
        out = f"{DIGITS[thousands]}千"
        if remainder:
            if remainder < 100:
                out += "零"
            out += small_integer(remainder)
        return out
    return "".join(DIGITS[int(char)] for char in str(number))


def number_string(raw):
    raw = str(raw)
    if len(raw) == 4 and raw.isdigit() and 1900 <= int(raw) <= 2099:
        return "".join(DIGITS[int(char)] for char in raw)
    if raw.isdigit() and int(raw) < 10000:
        return small_integer(int(raw))
    if raw.isdigit():
        return "".join(DIGITS[int(char)] for char in raw)
    return raw


def number_for_speech(match):
    raw = match.group(0).replace(",", "")
    if "." in raw:
        whole, fraction = raw.split(".", 1)
        return f"{number_string(whole)}點{''.join(DIGITS[int(c)] for c in fraction)}"
    return number_string(raw)


def normalize_for_tts(value):
    text = clean(value)
    text = re.sub(r"[「『“\"]?double[\-‐‑–— ]?tap[」』”\"]?", "二次打擊", text, flags=re.IGNORECASE)
    text = re.sub(r"\bReuters\b", "路透社", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAssociated Press\b", "美聯社", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAP\b", "美聯社", text)
    text = re.sub(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?", number_for_speech, text)
    text = text.replace("%", "百分比")
    text = text.replace("£", "英鎊").replace("€", "歐元").replace("$", "美元")
    text = text.replace("–", "，").replace("—", "，")
    return clean(text)


def speech_source_text(story):
    values = []
    seen = set()
    for key in FIELDS:
        value = clean(story.get(key))
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return "\n".join(values)


def content_sha(story):
    return hashlib.sha256(normalize_for_tts(speech_source_text(story)).encode("utf-8")).hexdigest()


def looks_like_story(obj):
    return isinstance(obj, dict) and clean(obj.get("title")) and any(clean(obj.get(key)) for key in FIELDS[1:])


def walk_stories(node):
    if isinstance(node, dict):
        if looks_like_story(node):
            yield node
        for value in node.values():
            yield from walk_stories(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_stories(value)


def load(path):
    if not path.is_file():
        return None, b""
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def collect_current():
    latest, latest_raw = load(Path("data/latest.json"))
    if not latest:
        raise RuntimeError("data/latest.json missing")
    date = latest.get("date")
    paths = [Path("data/latest.json"), Path("data/desk-latest.json"), Path("data/live.json"), Path("data/stocks-latest.json")]
    if date:
        paths += [Path(f"data/topic-more/{date}.json"), Path(f"data/editorial-overrides/{date}.json")]

    selected = {}
    order = []
    source_hash = hashlib.sha256()
    loaded = []
    for path in paths:
        data, raw = load(path)
        if data is None:
            continue
        loaded.append(path.as_posix())
        source_hash.update(path.as_posix().encode("utf-8") + b"\0" + raw + b"\0")
        for story in walk_stories(data):
            title = clean(story.get("title"))
            score = len(speech_source_text(story))
            if title not in selected:
                selected[title] = (story, score)
                order.append(title)
            elif score > selected[title][1]:
                selected[title] = (story, score)
    stories = [selected[title][0] for title in order]
    if len(stories) > 500:
        raise RuntimeError(f"current inventory unexpectedly large: {len(stories)}")

    lead_id = latest.get("leadId")
    latest_articles = latest.get("articles") or []
    lead_story = next((item for item in latest_articles if item.get("id") == lead_id), None) or (latest_articles[0] if latest_articles else None)
    lead_title = clean((lead_story or {}).get("title"))
    if lead_story and not lead_id:
        lead_id = lead_story.get("id")
    return latest, latest_raw, stories, lead_id, lead_title, source_hash.hexdigest(), loaded


def remote_valid(entry):
    audio = str((entry or {}).get("audio") or "")
    try:
        duration = float((entry or {}).get("durationSeconds") or 0)
        size = int((entry or {}).get("bytes") or 0)
    except (TypeError, ValueError):
        return False
    return audio.startswith(("https://", "http://")) and duration > 2 and size >= 50000


def index_entries(manifest):
    by_id, by_title = {}, {}
    for article_id, entry in (manifest.get("articles") or {}).items():
        if not isinstance(entry, dict) or not remote_valid(entry):
            continue
        by_id[article_id] = entry
        title = clean(entry.get("title"))
        if title:
            by_title[title] = entry
    return by_id, by_title


def main():
    if len(sys.argv) != 2:
        raise RuntimeError("usage: promote_cosyvoice_prepublish_fast.py <prepublish-worktree>")
    pre_root = Path(sys.argv[1])
    pre_path = pre_root / "data/prepublish-tts-manifest.json"
    pre = json.loads(pre_path.read_text(encoding="utf-8")) if pre_path.is_file() else {}
    if pre and (pre.get("engine") != "ASLP-lab/Cosyvoice2-Yue" or pre.get("voice") != "F01 female reference" or pre.get("language") != "yue-HK"):
        raise RuntimeError("prepublish manifest is not approved F01 yue-HK")

    previous = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
    pre_by_id, pre_by_title = index_entries(pre)
    old_by_id, old_by_title = index_entries(previous)
    latest, latest_raw, stories, lead_id, lead_title, source_set_sha, loaded_paths = collect_current()

    entries = {}
    promoted = 0
    reused = 0
    last_promoted = None
    for story in stories:
        article_id = story_identity(story)
        title = clean(story.get("title"))
        digest = content_sha(story)
        candidate = pre_by_id.get(article_id) or pre_by_title.get(title)
        source = "pre"
        if not candidate or candidate.get("contentSha256") != digest:
            candidate = old_by_id.get(article_id) or old_by_title.get(title)
            source = "old"
        if not candidate or candidate.get("contentSha256") != digest or not remote_valid(candidate):
            continue
        entry = dict(candidate)
        entry.update({"articleId": article_id, "title": title, "contentSha256": digest, "wavEncoding": "PCM16"})
        entries[article_id] = entry
        if source == "pre":
            promoted += 1
            last_promoted = entry
        else:
            reused += 1

    collected = len(stories)
    available = len(entries)
    manifest = {
        "version": 3,
        "engine": "ASLP-lab/Cosyvoice2-Yue",
        "voice": "F01 female reference",
        "language": "yue-HK",
        "pronunciationPolicy": "cantonese-only",
        "instructionPolicy": "short-no-leak",
        "coveragePolicy": "progressive-current-news-f01-only",
        "generationMode": "per-article-immediate-10-way",
        "storageBackend": "github-release",
        "retentionHours": 48,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "multi-source-current-site",
        "sourceSha256": hashlib.sha256(latest_raw).hexdigest(),
        "sourceSetSha256": source_set_sha,
        "sourceFiles": loaded_paths,
        "date": latest.get("date"),
        "leadId": lead_id,
        "leadTitle": lead_title,
        "articleCount": available,
        "availableArticleCount": available,
        "collectedStoryCount": collected,
        "pendingArticleCount": max(0, collected - available),
        "coverageComplete": available == collected,
        "lastPublishedArticleId": (last_promoted or {}).get("articleId") or previous.get("lastPublishedArticleId"),
        "lastPublishedTitle": (last_promoted or {}).get("title") or previous.get("lastPublishedTitle"),
        "articles": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"COSYVOICE_FAST_PROMOTE_PASS promoted={promoted} reused={reused} ready={available}/{collected} pending={collected-available}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
