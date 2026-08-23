#!/usr/bin/env python3
import hashlib
import json
import os
import shutil
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path

import generate_cosyvoice_all as gen

MANIFEST = Path("data/tts-manifest.json")
LEAD_ALIAS = Path("assets/audio/cosyvoice/latest-lead.wav")
PUBLIC_AUDIO_BASE = os.environ.get("COSY_PUBLIC_AUDIO_BASE", "").strip().rstrip("/")


def is_remote_audio(value):
    return str(value or "").startswith(("https://", "http://"))


def wav_metadata(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size < 50000:
        raise RuntimeError(f"missing/invalid F01 WAV: {path}")
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise RuntimeError(f"F01 WAV is not PCM16: {path}")
        duration = wav.getnframes() / float(wav.getframerate())
    if duration <= 2:
        raise RuntimeError(f"F01 WAV too short: {path} duration={duration:.3f}")
    return round(duration, 3), path.stat().st_size


def remote_metadata(entry):
    try:
        duration = float(entry.get("durationSeconds") or 0)
        size = int(entry.get("bytes") or 0)
    except (TypeError, ValueError):
        raise RuntimeError("remote F01 metadata invalid")
    if duration <= 2 or size < 50000:
        raise RuntimeError("remote F01 metadata below minimum")
    return round(duration, 3), size


def normalize_existing_entry(entry, article_id, title, digest):
    audio = str(entry.get("audio") or "")
    if is_remote_audio(audio):
        duration, size = remote_metadata(entry)
    else:
        duration, size = wav_metadata(audio)
    out = dict(entry)
    out.update({
        "articleId": article_id,
        "title": title,
        "contentSha256": digest,
        "durationSeconds": duration,
        "bytes": size,
        "wavEncoding": "PCM16",
    })
    return out


def reusable_previous(previous, story, digest):
    title = gen.clean(story.get("title"))
    old = gen.previous_entry_for_title(previous, title)
    if old and old.get("contentSha256") == digest and is_remote_audio(old.get("audio")):
        try:
            remote_metadata(old)
            return old
        except Exception:
            pass
    return gen.reusable_entry(previous, story, digest)


def main():
    if len(sys.argv) != 2:
        raise RuntimeError("usage: publish_cosyvoice_article.py <shard-json>")

    shard_path = Path(sys.argv[1])
    shard = json.loads(shard_path.read_text(encoding="utf-8"))
    if shard.get("engine") != "ASLP-lab/Cosyvoice2-Yue":
        raise RuntimeError("shard is not CosyVoice2-Yue")
    if shard.get("voice") != "F01 female reference" or shard.get("language") != "yue-HK":
        raise RuntimeError("shard is not F01 yue-HK")

    raw_entries = shard.get("entries") or {}
    if len(raw_entries) == 0:
        print("COSYVOICE_IMMEDIATE_PUBLISH_NOOP no generated entry in this worker", flush=True)
        return 0
    if len(raw_entries) != 1:
        raise RuntimeError(f"immediate publisher requires exactly one generated article, got {len(raw_entries)}")

    generated_id, raw_generated = next(iter(raw_entries.items()))
    generated = dict(raw_generated)
    remote_input = bool(generated.pop("remoteAudio", False))
    artifact_path = Path(str(generated.pop("artifactAudio", ""))) if not remote_input else None

    if remote_input:
        if not is_remote_audio(generated.get("audio")):
            raise RuntimeError("remote prebuilt F01 entry has no public audio URL")
        artifact_duration, artifact_size = remote_metadata(generated)
    else:
        if not artifact_path or not artifact_path.is_file():
            raise RuntimeError(f"generated artifact WAV missing: {artifact_path}")
        artifact_duration, artifact_size = wav_metadata(artifact_path)

    latest, latest_raw, stories, lead_id, lead_title, source_set_sha, loaded_paths = gen.collect_current_stories()
    current = {}
    current_by_title = {}
    for story in stories:
        article_id = gen.story_identity(story)
        title = gen.clean(story.get("title"))
        digest = gen.content_sha(story)
        item = {"story": story, "articleId": article_id, "title": title, "contentSha256": digest}
        current[article_id] = item
        current_by_title[title] = item

    wanted = current.get(generated_id) or current_by_title.get(gen.clean(generated.get("title")))
    if not wanted or wanted["contentSha256"] != generated.get("contentSha256"):
        print(
            "COSYVOICE_IMMEDIATE_PUBLISH_STALE "
            f"article={generated.get('title')} generated_sha={generated.get('contentSha256')}",
            flush=True,
        )
        return 0

    expected_path = gen.target_path(wanted["story"], wanted["contentSha256"])
    if remote_input:
        public_audio = str(generated.get("audio"))
        final_duration, final_size = artifact_duration, artifact_size
    elif PUBLIC_AUDIO_BASE:
        public_audio = f"{PUBLIC_AUDIO_BASE}/{expected_path.name}"
        final_duration, final_size = artifact_duration, artifact_size
    else:
        final_path = Path(str(generated.get("audio") or ""))
        if final_path.as_posix() != expected_path.as_posix():
            raise RuntimeError(f"generated target path mismatch: {final_path} != {expected_path}")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(artifact_path, final_path)
        final_duration, final_size = wav_metadata(final_path)
        if final_size != artifact_size:
            raise RuntimeError("copied F01 WAV byte size changed")
        public_audio = final_path.as_posix()

    published_at = datetime.now(timezone.utc).isoformat()
    generated.update({
        "articleId": wanted["articleId"],
        "title": wanted["title"],
        "audio": public_audio,
        "wavEncoding": "PCM16",
        "contentSha256": wanted["contentSha256"],
        "durationSeconds": final_duration,
        "bytes": final_size,
        "publishedAt": published_at,
    })

    previous = gen.load_previous_manifest()
    entries = {}
    newly_added = False
    for story in stories:
        article_id = gen.story_identity(story)
        title = gen.clean(story.get("title"))
        digest = gen.content_sha(story)

        if article_id == wanted["articleId"] or (title == wanted["title"] and digest == wanted["contentSha256"]):
            entries[article_id] = generated
            newly_added = True
            continue

        old = reusable_previous(previous, story, digest)
        if old:
            entries[article_id] = normalize_existing_entry(old, article_id, title, digest)
            continue

        if gen.can_reuse_legacy_lead(previous, latest_raw, story, lead_title):
            legacy = gen.previous_entry_for_title(previous, lead_title)
            if legacy:
                entries[article_id] = normalize_existing_entry(legacy, article_id, title, digest)

    if not newly_added:
        raise RuntimeError("generated F01 article was not added to current manifest")

    lead_entry = entries.get(lead_id)
    if not lead_entry:
        lead_entry = next((entry for entry in entries.values() if gen.clean(entry.get("title")) == lead_title), None)
    if lead_entry and not is_remote_audio(lead_entry.get("audio")):
        lead_path = Path(str(lead_entry.get("audio") or ""))
        LEAD_ALIAS.parent.mkdir(parents=True, exist_ok=True)
        if lead_path.is_file() and lead_path.resolve() != LEAD_ALIAS.resolve():
            shutil.copyfile(lead_path, LEAD_ALIAS)
            wav_metadata(LEAD_ALIAS)

    collected = len(stories)
    available = len(entries)
    manifest = {
        "version": 3,
        "engine": "ASLP-lab/Cosyvoice2-Yue",
        "voice": "F01 female reference",
        "language": "yue-HK",
        "pronunciationPolicy": "cantonese-only",
        "instructionPolicy": "short-no-leak",
        "coveragePolicy": "progressive-current-news-f01-only",
        "generationMode": "per-article-immediate-10-way",
        "storageBackend": "github-release" if PUBLIC_AUDIO_BASE or any(is_remote_audio(e.get("audio")) for e in entries.values()) else "git-tree",
        "retentionHours": 48,
        "generatedAt": published_at,
        "lastVoicePublishedAt": published_at,
        "source": "multi-source-current-site",
        "sourceSha256": hashlib.sha256(latest_raw).hexdigest(),
        "sourceSetSha256": source_set_sha,
        "sourceFiles": loaded_paths,
        "date": latest.get("date"),
        "leadId": lead_id,
        "leadTitle": lead_title,
        "articleCount": available,
        "availableArticleCount": available,
        "collectedStoryCount": collected,
        "pendingArticleCount": max(0, collected - available),
        "coverageComplete": available == collected,
        "lastPublishedArticleId": wanted["articleId"],
        "lastPublishedTitle": wanted["title"],
        "articles": entries,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        "COSYVOICE_IMMEDIATE_PUBLISH_PASS "
        f"article={wanted['articleId']} available={available}/{collected} pending={manifest['pendingArticleCount']} "
        f"published_at={published_at} duration={artifact_duration:.3f}s bytes={artifact_size} "
        f"storage={manifest['storageBackend']} source_set_sha256={source_set_sha}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
