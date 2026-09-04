#!/usr/bin/env python3
"""Validate that current published newsroom stories have current Canto Nano audio.

This is an outcome validator, not a workflow-status validator.  It rebuilds the
same current story set and content hashes used by the Canto Nano producer and
compares those expectations against data/tts-manifest.json.  Therefore an old
manifest cannot claim HEALTHY merely because its own counters say 239/239.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tts_hktrad_v3 as hktrad

FIELDS = (
    "title", "dek", "summary", "body", "context", "background",
    "why", "whyImportant", "watchNext", "nextStep",
)
EXPECTED_ENGINE = "typangaa/canto-tts-nano"
EXPECTED_NAMESPACE = "cnf4"
EXPECTED_LANGUAGE_GATE = "hk-cantonese-english-codeswitch-allowed"


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def story_id(story: dict[str, Any]) -> str:
    raw = story.get("id") or story.get("articleId") or story.get("storyId")
    if raw:
        value = re.sub(r"[^a-z0-9._-]+", "-", clean(raw).lower()).strip("-._")
        return value[:72] or "story"
    return "story-" + hashlib.sha256(clean(story.get("title")).encode()).hexdigest()[:16]


def is_story(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and bool(clean(value.get("title")))
        and any(clean(value.get(key)) for key in FIELDS[1:])
    )


def walk(value: Any):
    if isinstance(value, dict):
        if is_story(value):
            yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError(f"{path}: expected JSON object")
    return data


def source_paths(date: str | None) -> list[Path]:
    paths = [
        Path("data/latest.json"),
        Path("data/desk-latest.json"),
        Path("data/live.json"),
        Path("data/stocks-latest.json"),
    ]
    if date:
        paths.extend([
            Path(f"data/topic-more/{date}.json"),
            Path(f"data/editorial-overrides/{date}.json"),
        ])
    return paths


def source_text(story: dict[str, Any]) -> str:
    seen: set[str] = set()
    values: list[str] = []
    for key in FIELDS:
        value = clean(story.get(key))
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return "\n".join(values)


def content_digest(story: dict[str, Any]) -> str:
    # The production wrapper replaces canto_nano_prod.hktrad with tts_hktrad_v3,
    # so this is exactly the digest semantics used by current cnf4 generation.
    return hashlib.sha256(hktrad.localize(source_text(story)).encode()).hexdigest()


def collect_current() -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    latest = read_json(Path("data/latest.json"))
    if not latest:
        raise RuntimeError("data/latest.json missing")

    chosen: dict[str, tuple[dict[str, Any], int]] = {}
    order: list[str] = []
    loaded: list[str] = []
    for path in source_paths(clean(latest.get("date")) or None):
        data = read_json(path)
        if data is None:
            continue
        loaded.append(path.as_posix())
        for story in walk(data):
            title = clean(story.get("title"))
            score = len(source_text(story))
            if title not in chosen:
                chosen[title] = (story, score)
                order.append(title)
            elif score > chosen[title][1]:
                chosen[title] = (story, score)

    stories = [chosen[title][0] for title in order]
    articles = latest.get("articles") if isinstance(latest.get("articles"), list) else []
    lead = next((x for x in articles if isinstance(x, dict) and x.get("id") == latest.get("leadId")), None)
    if lead is None:
        lead = next((x for x in articles if isinstance(x, dict)), None)
    if not lead:
        raise RuntimeError("no lead story")
    lead_title = clean(lead.get("title"))
    stories.sort(key=lambda s: 0 if clean(s.get("title")) == lead_title else 1)
    return latest, stories, loaded


def validate() -> dict[str, Any]:
    latest, stories, loaded = collect_current()
    manifest = read_json(Path("data/tts-manifest.json")) or {}
    articles = manifest.get("articles") if isinstance(manifest.get("articles"), dict) else {}

    expected: dict[str, dict[str, str]] = {}
    for story in stories:
        sid = story_id(story)
        expected[sid] = {
            "title": clean(story.get("title")),
            "contentSha256": content_digest(story),
        }

    missing: list[str] = []
    stale: list[str] = []
    invalid: list[str] = []
    playable = 0
    for sid, want in expected.items():
        entry = articles.get(sid)
        if not isinstance(entry, dict):
            # Backward-compatible lookup for manifests that may have been keyed
            # differently while still carrying articleId inside the entry.
            entry = next(
                (e for e in articles.values() if isinstance(e, dict) and clean(e.get("articleId")) == sid),
                None,
            )
        if not isinstance(entry, dict):
            missing.append(sid)
            continue
        if clean(entry.get("contentSha256")) != want["contentSha256"]:
            stale.append(sid)
            continue
        audio = clean(entry.get("audio"))
        if (
            not audio
            or f"-{EXPECTED_NAMESPACE}-" not in audio
            or entry.get("contentComplete") is not True
            or clean(entry.get("languageGate")) != EXPECTED_LANGUAGE_GATE
        ):
            invalid.append(sid)
            continue
        playable += 1

    engine_ok = clean(manifest.get("engine")) == EXPECTED_ENGINE
    healthy = engine_ok and not missing and not stale and not invalid and playable == len(expected)
    lead_id = story_id(stories[0]) if stories else None

    return {
        "schemaVersion": 1,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "healthy": healthy,
        "engineOk": engine_ok,
        "expectedNamespace": EXPECTED_NAMESPACE,
        "expectedLanguageGate": EXPECTED_LANGUAGE_GATE,
        "editionDate": latest.get("date"),
        "sourceFiles": loaded,
        "currentStoryCount": len(expected),
        "currentPlayableCount": playable,
        "missingCount": len(missing),
        "staleContentCount": len(stale),
        "invalidEntryCount": len(invalid),
        "missingArticleIds": missing[:50],
        "staleContentArticleIds": stale[:50],
        "invalidEntryArticleIds": invalid[:50],
        "leadArticleId": lead_id,
        "manifestGeneratedAt": manifest.get("generatedAt"),
        "manifestLastVoicePublishedAt": manifest.get("lastVoicePublishedAt"),
        "manifestSelfReportedCoverageComplete": manifest.get("coverageComplete"),
        "manifestSelfReportedAvailable": manifest.get("availableArticleCount"),
        "manifestSelfReportedCollected": manifest.get("collectedStoryCount"),
        "manifestSelfReportedPending": manifest.get("pendingArticleCount"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default="")
    parser.add_argument("--allow-unhealthy", action="store_true")
    args = parser.parse_args()
    result = validate()
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        Path(args.report).write_text(text, encoding="utf-8")
    print(text, end="")
    if result["healthy"] or args.allow_unhealthy:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
