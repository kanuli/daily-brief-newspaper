#!/usr/bin/env python3
"""Promote only exact-current F01 audio built under the current news-anchor policy."""
import json
from pathlib import Path

import generate_cosyvoice_lead as voice_base
import promote_cosyvoice_prepublish_fast as legacy

POLICY = voice_base.VOICE_POLICY_VERSION
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
        "inferenceMode": voice_base.VOICE_INFERENCE_MODE,
        "speed": voice_base.VOICE_SPEED,
    })
    articles = data.get("articles") or {}
    articles = {
        article_id: entry for article_id, entry in articles.items()
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
