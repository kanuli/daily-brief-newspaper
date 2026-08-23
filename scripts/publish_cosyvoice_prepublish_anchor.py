#!/usr/bin/env python3
"""Prepublish manifest publisher for the current F01 policy."""
import json
from pathlib import Path

import generate_cosyvoice_lead as voice_base
import publish_cosyvoice_prepublish as legacy

POLICY = "f01-news-anchor-v7-short-prompt-bistream-hktrad"
REFERENCE_POLICY = "user-approved-nvidia-anchor-v1"
REFERENCE_ASSET = "ai-nvidia-server-price-0800-79489f0afc38.wav"
REFERENCE_START_SECONDS = 10.0
REFERENCE_DURATION_SECONDS = 5.0
INITIAL_CONDITIONING_POLICY = "short-reference-bistream"
LANGUAGE_GATE = "residual-latin-zero"
SEGMENT_POLICY = "single-inference-per-article"


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
        and int(entry.get("segmentCount") or 0) == 1
    )


def _policy_valid_existing(entry, digest):
    if not _valid_policy_entry(entry, digest):
        return False
    return legacy.valid_existing(entry, digest)


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
        "inferenceMode": voice_base.VOICE_INFERENCE_MODE,
        "speed": voice_base.VOICE_SPEED,
        "languageGate": LANGUAGE_GATE,
        "segmentPolicy": SEGMENT_POLICY,
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
