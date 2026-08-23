#!/usr/bin/env python3
"""Promote only exact-current F01 audio without loading the TTS runtime."""
import json
from pathlib import Path

import cosyvoice_policy as voice_policy
import promote_cosyvoice_prepublish_fast as legacy

POLICY = voice_policy.POLICY
INFERENCE_MODE = voice_policy.INFERENCE_MODE
VOICE_SPEED = voice_policy.VOICE_SPEED
REFERENCE_DURATION_SECONDS = voice_policy.REFERENCE_DURATION_SECONDS
INITIAL_CONDITIONING_POLICY = voice_policy.INITIAL_CONDITIONING_POLICY
LANGUAGE_GATE = voice_policy.LANGUAGE_GATE
SEGMENT_POLICY = voice_policy.SEGMENT_POLICY
PACING_POLICY = voice_policy.PACING_POLICY
TEMPO_POLICY = voice_policy.TEMPO_POLICY
_ORIGINAL_INDEX = legacy.index_entries


def _valid_entry(entry):
    try:
        reference_duration = float(entry.get("referenceDurationSeconds") or 0) if isinstance(entry, dict) else 0
    except (TypeError, ValueError):
        return False
    return (
        isinstance(entry, dict)
        and entry.get("prosodyPolicy") == POLICY
        and entry.get("initialConditioningPolicy") == INITIAL_CONDITIONING_POLICY
        and reference_duration == REFERENCE_DURATION_SECONDS
        and entry.get("languageGate") == LANGUAGE_GATE
        and entry.get("segmentPolicy") == SEGMENT_POLICY
        and entry.get("pacingPolicy") == PACING_POLICY
        and entry.get("tempoPolicy") == TEMPO_POLICY
        and int(entry.get("segmentCount") or 0) == 1
    )


def _policy_index_entries(manifest):
    if not isinstance(manifest, dict) or manifest.get("prosodyPolicy") != POLICY:
        return {}, {}
    by_id, by_title = _ORIGINAL_INDEX(manifest)
    by_id = {k: v for k, v in by_id.items() if _valid_entry(v)}
    by_title = {k: v for k, v in by_title.items() if _valid_entry(v)}
    return by_id, by_title


def _stamp_manifest():
    path = Path("data/tts-manifest.json")
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update({
        "instructionPolicy": "none-reference-only",
        "prosodyPolicy": POLICY,
        "inferenceMode": INFERENCE_MODE,
        "speed": VOICE_SPEED,
        "referenceDurationSeconds": REFERENCE_DURATION_SECONDS,
        "initialConditioningPolicy": INITIAL_CONDITIONING_POLICY,
        "languageGate": LANGUAGE_GATE,
        "segmentPolicy": SEGMENT_POLICY,
        "pacingPolicy": PACING_POLICY,
        "tempoPolicy": TEMPO_POLICY,
    })
    articles = {
        article_id: entry for article_id, entry in (data.get("articles") or {}).items()
        if _valid_entry(entry)
    }
    data["articles"] = articles
    available = len(articles)
    total = int(data.get("collectedStoryCount") or available)
    data["articleCount"] = available
    data["availableArticleCount"] = available
    data["pendingArticleCount"] = max(0, total - available)
    data["coverageComplete"] = available == total
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


legacy.index_entries = _policy_index_entries

if __name__ == "__main__":
    code = legacy.main()
    _stamp_manifest()
    raise SystemExit(code)
