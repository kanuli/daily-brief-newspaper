#!/usr/bin/env python3
"""Promote exact-current F01 audio without importing the heavy TTS runtime."""
import json
from pathlib import Path

import promote_cosyvoice_prepublish_fast as legacy

POLICY = "f01-news-anchor-v5-golden-hktrad"
INFERENCE_MODE = "cross-lingual-reference-only"
VOICE_SPEED = 1.0
_ORIGINAL_INDEX = legacy.index_entries


def _policy_index_entries(manifest):
    if not isinstance(manifest, dict) or manifest.get("prosodyPolicy") != POLICY:
        return {}, {}
    by_id, by_title = _ORIGINAL_INDEX(manifest)
    by_id = {k: v for k, v in by_id.items() if isinstance(v, dict) and v.get("prosodyPolicy") == POLICY}
    by_title = {k: v for k, v in by_title.items() if isinstance(v, dict) and v.get("prosodyPolicy") == POLICY}
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
    })
    articles = {
        article_id: entry for article_id, entry in (data.get("articles") or {}).items()
        if isinstance(entry, dict) and entry.get("prosodyPolicy") == POLICY
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
