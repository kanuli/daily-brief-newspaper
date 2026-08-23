#!/usr/bin/env python3
"""Immediate production manifest publisher for the stable-tempo F01 news-anchor policy."""
import json
from pathlib import Path

import generate_cosyvoice_lead as voice_base
import publish_cosyvoice_article as legacy

POLICY = "f01-news-anchor-v3-stable-tempo"


def _policy_reusable_previous(previous, story, digest):
    title = legacy.gen.clean(story.get("title"))
    old = legacy.gen.previous_entry_for_title(previous, title)
    if not old or old.get("contentSha256") != digest or old.get("prosodyPolicy") != POLICY:
        return None
    audio = str(old.get("audio") or "")
    if audio.startswith(("https://", "http://")):
        try:
            legacy.remote_metadata(old)
            return old
        except Exception:
            return None
    return None


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


legacy.reusable_previous = _policy_reusable_previous
legacy.gen.can_reuse_legacy_lead = lambda *args, **kwargs: False

if __name__ == "__main__":
    code = legacy.main()
    _stamp_manifest()
    raise SystemExit(code)
