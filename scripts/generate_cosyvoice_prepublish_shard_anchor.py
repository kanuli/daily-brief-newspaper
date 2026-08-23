#!/usr/bin/env python3
"""Prepublish shard generation using the current natural-newsreader F01 policy."""
import generate_cosyvoice_lead as voice_base
import generate_cosyvoice_prepublish_shard as legacy

POLICY = voice_base.VOICE_POLICY_VERSION


def _policy_reusable(previous, story, digest):
    article_id = legacy.gen.story_identity(story)
    title = legacy.gen.clean(story.get("title"))
    old = (previous.get("articles") or {}).get(article_id)
    if not old:
        old = next((e for e in (previous.get("articles") or {}).values() if legacy.gen.clean(e.get("title")) == title), None)
    if not old or old.get("contentSha256") != digest or old.get("prosodyPolicy") != POLICY:
        return False
    audio = str(old.get("audio") or "")
    if audio.startswith(("https://", "http://")):
        try:
            return int(old.get("bytes") or 0) >= 50000 and float(old.get("durationSeconds") or 0) > 2
        except (TypeError, ValueError):
            return False
    return False


_original_synth = legacy.gen.synthesize_story


def _policy_synth(model, prompt, story, path):
    meta = _original_synth(model, prompt, story, path)
    meta.update({
        "prosodyPolicy": POLICY,
        "inferenceMode": voice_base.VOICE_INFERENCE_MODE,
        "speed": voice_base.VOICE_SPEED,
        "instructionPolicy": "none-reference-only",
    })
    return meta


legacy.reusable = _policy_reusable
legacy.gen.synthesize_story = _policy_synth

if __name__ == "__main__":
    raise SystemExit(legacy.main())
