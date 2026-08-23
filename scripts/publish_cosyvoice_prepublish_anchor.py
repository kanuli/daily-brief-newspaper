#!/usr/bin/env python3
"""Prepublish manifest publisher for the user-approved golden F01 policy."""
import json
from pathlib import Path

import generate_cosyvoice_lead as voice_base
import publish_cosyvoice_prepublish as legacy

POLICY = "f01-news-anchor-v4-golden-nvidia"
REFERENCE_POLICY = "user-approved-nvidia-anchor-v1"
REFERENCE_ASSET = "ai-nvidia-server-price-0800-79489f0afc38.wav"


def _policy_valid_existing(entry, digest):
    if not entry or entry.get("contentSha256") != digest or entry.get("prosodyPolicy") != POLICY:
        return False
    if entry.get("referencePolicy") != REFERENCE_POLICY:
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
        "prosodyPolicy": POLICY,
        "inferenceMode": voice_base.VOICE_INFERENCE_MODE,
        "speed": voice_base.VOICE_SPEED,
    })
    articles = {
        article_id: entry for article_id, entry in (data.get("articles") or {}).items()
        if isinstance(entry, dict)
        and entry.get("prosodyPolicy") == POLICY
        and entry.get("referencePolicy") == REFERENCE_POLICY
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
