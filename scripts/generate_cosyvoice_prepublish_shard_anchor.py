#!/usr/bin/env python3
"""Prepublish shard generation using the current natural-newsreader F01 policy."""
import re

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


def _anchor_script_segments(story):
    budget = int(getattr(legacy.gen, "ARTICLE_TEXT_LIMIT", 260) or 260)
    values = []
    seen = set()

    def add(value):
        raw = legacy.gen.clean(value)
        if not raw or raw in seen:
            return
        seen.add(raw)
        values.append(raw)

    add(story.get("title"))
    add(story.get("dek"))
    add(story.get("summary"))
    paragraphs = [legacy.gen.clean(p) for p in re.split(r"\n\s*\n", str(story.get("body") or "")) if legacy.gen.clean(p)]
    for paragraph in paragraphs[:2]:
        add(paragraph)
    add(story.get("context") or story.get("background"))
    add(story.get("why") or story.get("whyImportant"))
    add(story.get("watchNext") or story.get("nextStep"))

    chunks = []
    used = 0
    for raw in values:
        text = voice_base.normalize_for_tts(raw)
        if not text or used >= budget:
            continue
        remaining = budget - used
        text = text[:remaining]
        used += len(text)
        if text and text[-1] not in "。！？!?…":
            text += "。"
        chunks.append(text)

    script = "".join(chunks)
    if len(script) < 8:
        raise RuntimeError(f"story text too short for TTS: {story.get('title')!r}")
    pieces = voice_base.split_for_tts(script, max_chars=150)
    return [
        {
            "role": "news",
            "text": piece,
            "pause": 0.30 if index < len(pieces) - 1 else 0.42,
        }
        for index, piece in enumerate(pieces)
    ]


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
legacy.gen.build_article_segments = _anchor_script_segments
legacy.gen.synthesize_story = _policy_synth

if __name__ == "__main__":
    raise SystemExit(legacy.main())
