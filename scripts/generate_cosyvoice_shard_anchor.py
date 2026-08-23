#!/usr/bin/env python3
"""Generate one F01 shard using the current natural-newsreader policy.

This wrapper intentionally invalidates every pre-v2 voice so old irregular or
instruction-leaking audio cannot be reused after the policy change.
"""
import generate_cosyvoice_lead as voice_base
import generate_cosyvoice_shard as legacy

POLICY = voice_base.VOICE_POLICY_VERSION


def _policy_remote_reusable(previous, story, digest):
    old = legacy.gen.previous_entry_for_title(previous, legacy.gen.clean(story.get("title")))
    if not old or old.get("contentSha256") != digest or old.get("prosodyPolicy") != POLICY:
        return False
    audio = str(old.get("audio") or "")
    if not audio.startswith(("https://", "http://")):
        return False
    try:
        return int(old.get("bytes") or 0) >= 50000 and float(old.get("durationSeconds") or 0) > 2
    except (TypeError, ValueError):
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


legacy.remote_reusable = _policy_remote_reusable
legacy.gen.synthesize_story = _policy_synth
legacy.gen.can_reuse_legacy_lead = lambda *args, **kwargs: False

if __name__ == "__main__":
    raise SystemExit(legacy.main())
