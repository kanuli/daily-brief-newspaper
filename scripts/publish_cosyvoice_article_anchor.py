#!/usr/bin/env python3
"""Immediate production manifest publisher for the current F01 policy."""
import json
from pathlib import Path

import cosyvoice_policy as voice_policy
import generate_cosyvoice_lead as voice_base
import publish_cosyvoice_article as legacy

POLICY = voice_policy.POLICY
REFERENCE_POLICY = voice_policy.REFERENCE_POLICY
REFERENCE_ASSET = voice_policy.REFERENCE_ASSET
REFERENCE_START_SECONDS = voice_policy.REFERENCE_START_SECONDS
REFERENCE_DURATION_SECONDS = voice_policy.REFERENCE_DURATION_SECONDS
INITIAL_CONDITIONING_POLICY = voice_policy.INITIAL_CONDITIONING_POLICY
LANGUAGE_GATE = voice_policy.LANGUAGE_GATE
SEGMENT_POLICY = voice_policy.SEGMENT_POLICY


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


def _policy_reusable_previous(previous, story, digest):
    title = legacy.gen.clean(story.get("title"))
    old = legacy.gen.previous_entry_for_title(previous, title)
    if not _valid_policy_entry(old, digest):
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
    newest = max(
        ((str(entry.get("publishedAt") or ""), article_id, entry) for article_id, entry in articles.items() if entry.get("publishedAt")),
        default=None,
    )
    if newest:
        data["lastVoicePublishedAt"] = newest[0]
        data["lastPublishedArticleId"] = newest[1]
        data["lastPublishedTitle"] = newest[2].get("title") or ""
    else:
        data["lastVoicePublishedAt"] = ""
        data["lastPublishedArticleId"] = ""
        data["lastPublishedTitle"] = ""
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
