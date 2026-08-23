#!/usr/bin/env python3
"""Prepublish shard generation using the same stable-tempo policy as production."""
import generate_cosyvoice_shard_anchor as anchor
import generate_cosyvoice_prepublish_shard as legacy

POLICY = anchor.POLICY


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


legacy.reusable = _policy_reusable
legacy.gen.build_article_segments = anchor._anchor_script_segments
legacy.gen.synthesize_story = anchor._policy_synth
legacy.gen.can_reuse_legacy_lead = lambda *args, **kwargs: False

if __name__ == "__main__":
    raise SystemExit(legacy.main())
