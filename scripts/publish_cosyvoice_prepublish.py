#!/usr/bin/env python3
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import generate_cosyvoice_all as gen

DRAFT = Path("data/prepublish.json")
MANIFEST = Path("data/prepublish-tts-manifest.json")
LEAD_ALIAS = Path("assets/audio/cosyvoice/prepublish-latest-lead.wav")


def collect_draft():
    data = json.loads(DRAFT.read_text(encoding="utf-8"))
    if data.get("status") != "VERIFIED_DRAFT":
        raise RuntimeError("prepublish file is not VERIFIED_DRAFT")
    stories = list(gen.walk_stories(data.get("articles") or []))
    return data, stories


def main():
    if len(sys.argv) != 2:
        raise RuntimeError("usage: publish_cosyvoice_prepublish.py <shard-json>")
    shard = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if shard.get("engine") != "ASLP-lab/Cosyvoice2-Yue" or shard.get("voice") != "F01 female reference" or shard.get("language") != "yue-HK":
        raise RuntimeError("invalid prepublish F01 shard")
    raw_entries = shard.get("entries") or {}
    if not raw_entries:
        print("COSYVOICE_PREPUBLISH_NOOP no generated entry", flush=True)
        return 0
    if len(raw_entries) != 1:
        raise RuntimeError("prepublish publisher requires one entry")

    draft, stories = collect_draft()
    generated_id, generated = next(iter(raw_entries.items()))
    generated = dict(generated)
    artifact = Path(str(generated.pop("artifactAudio", "")))
    if not artifact.is_file() or artifact.stat().st_size < 50000:
        raise RuntimeError(f"missing generated artifact: {artifact}")

    current = {}
    current_by_title = {}
    for story in stories:
        article_id = gen.story_identity(story)
        title = gen.clean(story.get("title"))
        digest = gen.content_sha(story)
        item = (story, article_id, title, digest)
        current[article_id] = item
        current_by_title[title] = item

    wanted = current.get(generated_id) or current_by_title.get(gen.clean(generated.get("title")))
    if not wanted or wanted[3] != generated.get("contentSha256"):
        print("COSYVOICE_PREPUBLISH_STALE generated voice no longer matches verified draft", flush=True)
        return 0

    story, article_id, title, digest = wanted
    final_path = gen.target_path(story, digest)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(artifact, final_path)
    duration, size = gen.wav_metadata(final_path)

    previous = {}
    if MANIFEST.is_file():
        try:
            previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            previous = {}

    entries = {}
    for item in stories:
        item_id = gen.story_identity(item)
        item_title = gen.clean(item.get("title"))
        item_digest = gen.content_sha(item)
        item_path = gen.target_path(item, item_digest)
        if not item_path.is_file() or item_path.stat().st_size < 50000:
            continue
        try:
            item_duration, item_size = gen.wav_metadata(item_path)
        except Exception:
            continue
        old = (previous.get("articles") or {}).get(item_id) or {}
        entries[item_id] = {
            **old,
            "articleId": item_id,
            "title": item_title,
            "audio": item_path.as_posix(),
            "wavEncoding": "PCM16",
            "contentSha256": item_digest,
            "durationSeconds": round(item_duration, 3),
            "bytes": item_size,
        }
        if item_id == article_id:
            entries[item_id].update({k: v for k, v in generated.items() if k not in {"audio", "articleId", "title", "contentSha256"}})

    lead_id = draft.get("leadId") or (gen.story_identity(stories[0]) if stories else None)
    lead_entry = entries.get(lead_id)
    if lead_entry:
        lead_path = Path(lead_entry["audio"])
        if lead_path.is_file():
            LEAD_ALIAS.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(lead_path, LEAD_ALIAS)

    total = len(stories)
    available = len(entries)
    manifest = {
        "version": 1,
        "engine": "ASLP-lab/Cosyvoice2-Yue",
        "voice": "F01 female reference",
        "language": "yue-HK",
        "mode": "verified-draft-prepublish",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "draftId": draft.get("draftId"),
        "targetPublication": draft.get("targetPublication"),
        "articleCount": available,
        "availableArticleCount": available,
        "collectedStoryCount": total,
        "pendingArticleCount": max(0, total - available),
        "coverageComplete": available == total,
        "leadId": lead_id,
        "lastPreparedArticleId": article_id,
        "lastPreparedTitle": title,
        "articles": entries,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"COSYVOICE_PREPUBLISH_PASS article={article_id} ready={available}/{total} pending={total-available} duration={duration:.3f}s bytes={size}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
