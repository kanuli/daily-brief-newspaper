#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path

import generate_cosyvoice_all as gen
# Importing the production anchor patches the shared generate_cosyvoice_all
# module to the current F01 policy: speech-only HK-Traditional localization,
# residual-Latin blocking, one inference per article, and the approved reference.
import generate_cosyvoice_shard_anchor as anchor

DRAFT = Path(os.environ.get("COSY_PREPUBLISH_JSON", "data/prepublish.json"))
MANIFEST = Path(os.environ.get("COSY_PREPUBLISH_MANIFEST", "data/prepublish-tts-manifest.json"))
SHARD_INDEX = int(os.environ.get("COSY_SHARD_INDEX", "0"))
SHARD_COUNT = int(os.environ.get("COSY_SHARD_COUNT", "10"))
OUT_DIR = Path(os.environ.get("COSY_SHARD_OUT_DIR", "artifacts/cosyvoice-prepublish"))


def stable_slot(story):
    digest = hashlib.sha256(gen.story_identity(story).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % SHARD_COUNT


def collect_draft_stories():
    if not DRAFT.is_file():
        raise RuntimeError(f"prepublish draft missing: {DRAFT}")
    data = json.loads(DRAFT.read_text(encoding="utf-8"))
    if data.get("status") != "VERIFIED_DRAFT":
        raise RuntimeError("prepublish file is not VERIFIED_DRAFT")
    selected = {}
    order = []
    for story in gen.walk_stories(data.get("articles") or []):
        title = gen.clean(story.get("title"))
        if not title:
            continue
        score = len(gen.speech_source_text(story))
        if title not in selected:
            selected[title] = (story, score)
            order.append(title)
        elif score > selected[title][1]:
            selected[title] = (story, score)
    stories = [selected[t][0] for t in order]
    if not stories:
        raise RuntimeError("VERIFIED_DRAFT contains no voice-ready articles")
    return data, stories


def load_previous():
    if not MANIFEST.is_file():
        return {}
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if data.get("engine") != "ASLP-lab/Cosyvoice2-Yue" or data.get("voice") != "F01 female reference":
            return {}
        return data
    except Exception:
        return {}


def reusable(previous, story, digest):
    article_id = gen.story_identity(story)
    title = gen.clean(story.get("title"))
    old = (previous.get("articles") or {}).get(article_id)
    if not old:
        old = next((e for e in (previous.get("articles") or {}).values() if gen.clean(e.get("title")) == title), None)
    if not old or old.get("contentSha256") != digest:
        return False
    if old.get("prosodyPolicy") != anchor.POLICY or old.get("referencePolicy") != anchor.REFERENCE_POLICY:
        return False
    if old.get("languageGate") != "residual-latin-zero" or old.get("segmentPolicy") != "single-inference-per-article":
        return False
    audio = str(old.get("audio") or "")
    if audio.startswith(("https://", "http://")):
        try:
            return int(old.get("bytes") or 0) >= 50000 and float(old.get("durationSeconds") or 0) > 2
        except (TypeError, ValueError):
            return False
    path = Path(audio)
    if not path.is_file() or path.stat().st_size < 50000:
        return False
    try:
        duration, _ = gen.wav_metadata(path)
        return duration > 2
    except Exception:
        return False


def main():
    if SHARD_COUNT < 1 or not (0 <= SHARD_INDEX < SHARD_COUNT):
        raise RuntimeError(f"invalid shard {SHARD_INDEX}/{SHARD_COUNT}")
    draft, stories = collect_draft_stories()
    previous = load_previous()
    assigned = [s for s in stories if stable_slot(s) == SHARD_INDEX]
    missing = []
    for story in assigned:
        digest = gen.content_sha(story)
        final_path = gen.target_path(story, digest)
        if reusable(previous, story, digest):
            continue
        # Do not trust an unmanifested local WAV: policy provenance is unknown.
        missing.append((story, digest, final_path))

    selected = missing[:1]
    entries = {}
    if selected:
        story, digest, final_path = selected[0]
        model, prompt = gen.setup_model()
        artifact_path = OUT_DIR / "audio" / f"shard-{SHARD_INDEX}" / final_path.name
        meta = gen.synthesize_story(model, prompt, story, artifact_path)
        article_id = gen.story_identity(story)
        entries[article_id] = {
            "articleId": article_id,
            "title": gen.clean(story.get("title")),
            "audio": final_path.as_posix(),
            "artifactAudio": artifact_path.as_posix(),
            "wavEncoding": "PCM16",
            "contentSha256": digest,
            **meta,
        }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 2,
        "engine": "ASLP-lab/Cosyvoice2-Yue",
        "voice": "F01 female reference",
        "language": "yue-HK",
        "prosodyPolicy": anchor.POLICY,
        "draftId": draft.get("draftId"),
        "targetPublication": draft.get("targetPublication"),
        "shardIndex": SHARD_INDEX,
        "shardCount": SHARD_COUNT,
        "entries": entries,
    }
    out = OUT_DIR / f"shard-{SHARD_INDEX}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"COSYVOICE_PREPUBLISH_PLAN policy={anchor.POLICY} slot={SHARD_INDEX}/{SHARD_COUNT} "
        f"assigned={len(assigned)} missing={len(missing)} generated={len(entries)} draft={draft.get('draftId')}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
