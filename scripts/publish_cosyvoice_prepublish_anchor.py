#!/usr/bin/env python3
"""Prepublish manifest publisher for the current F01 policy."""
import json
from pathlib import Path

import cosyvoice_policy as voice_policy
import publish_cosyvoice_prepublish as legacy

POLICY = voice_policy.POLICY
REFERENCE_POLICY = voice_policy.REFERENCE_POLICY
REFERENCE_ASSET = voice_policy.REFERENCE_ASSET
REFERENCE_START_SECONDS = voice_policy.REFERENCE_START_SECONDS
REFERENCE_DURATION_SECONDS = voice_policy.REFERENCE_DURATION_SECONDS
INITIAL_CONDITIONING_POLICY = voice_policy.INITIAL_CONDITIONING_POLICY
LANGUAGE_GATE = voice_policy.LANGUAGE_GATE
SEGMENT_POLICY = voice_policy.SEGMENT_POLICY
PACING_POLICY = voice_policy.PACING_POLICY
TEMPO_POLICY = voice_policy.TEMPO_POLICY
_ORIGINAL_VALID_EXISTING = legacy.valid_existing


def _valid_policy_entry(entry, digest=None):
    if not isinstance(entry, dict):
        return False
    if digest is not None and entry.get("contentSha256") != digest:
        return False
    try:
        reference_duration = float(entry.get("referenceDurationSeconds") or 0)
    except (TypeError, ValueError):
        return False
    return (
        entry.get("prosodyPolicy") == POLICY
        and entry.get("referencePolicy") == REFERENCE_POLICY
        and entry.get("initialConditioningPolicy") == INITIAL_CONDITIONING_POLICY
        and reference_duration == REFERENCE_DURATION_SECONDS
        and entry.get("languageGate") == LANGUAGE_GATE
        and entry.get("segmentPolicy") == SEGMENT_POLICY
        and entry.get("pacingPolicy") == PACING_POLICY
        and entry.get("tempoPolicy") == TEMPO_POLICY
        and int(entry.get("segmentCount") or 0) == 1
    )


def _policy_valid_existing(entry, digest):
    if not _valid_policy_entry(entry, digest):
        return False
    return _ORIGINAL_VALID_EXISTING(entry, digest)


def _stamp_manifest():
    path = Path("data/prepublish-tts-manifest.json")
    if not path.is_file():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    data.update({
        "instructionPolicy": "none-reference-only",
        "referencePolicy": REFERENCE_POLICY,
        "referenceAsset": REFERENCE_ASSET,
        "referenceStartSeconds": REFERENCE_START_SECONDS,
        "referenceDurationSeconds": REFERENCE_DURATION_SECONDS,
        "initialConditioningPolicy": INITIAL_CONDITIONING_POLICY,
        "prosodyPolicy": POLICY,
        "inferenceMode": voice_policy.INFERENCE_MODE,
        "speed": voice_policy.VOICE_SPEED,
        "languageGate": LANGUAGE_GATE,
        "segmentPolicy": SEGMENT_POLICY,
        "pacingPolicy": PACING_POLICY,
        "tempoPolicy": TEMPO_POLICY,
    })
    articles = {
        article_id: entry for article_id, entry in (data.get("articles") or {}).items()
        if _valid_policy_entry(entry)
    }
    data["articles"] = articles
    available = len(articles)
    total = int(data.get("collectedStoryCount") or available)
    data["articleCount"] = available
    data["availableArticleCount"] = available
    data["pendingArticleCount"] = max(0, total - available)
    data["coverageComplete"] = available == total
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


legacy.valid_existing = _policy_valid_existing

if __name__ == "__main__":
    code = legacy.main()
    _stamp_manifest()
    raise SystemExit(code)
