#!/usr/bin/env python3
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import generate_cosyvoice_all as gen

SHARD_INDEX = int(os.environ.get("COSY_SHARD_INDEX", "0"))
SHARD_COUNT = int(os.environ.get("COSY_SHARD_COUNT", "1"))
EXPECTED_LIMIT = int(os.environ.get("COSY_SHARD_EXPECTED_LIMIT", "0"))
OUT_DIR = Path(os.environ.get("COSY_SHARD_OUT_DIR", "artifacts/cosyvoice-shards"))


def main():
    if SHARD_COUNT < 1 or SHARD_INDEX < 0 or SHARD_INDEX >= SHARD_COUNT:
        raise RuntimeError(f"invalid shard {SHARD_INDEX}/{SHARD_COUNT}")

    latest, latest_raw, stories, lead_id, lead_title, source_set_sha, loaded_paths = gen.collect_current_stories()
    if EXPECTED_LIMIT > 0:
        stories = stories[:EXPECTED_LIMIT]
        print(f"TEST LIMIT: shard expected article set limited to {len(stories)} stories", flush=True)
    previous = gen.load_previous_manifest()

    expected = []
    missing = []
    reusable = 0
    for story in stories:
        digest = gen.content_sha(story)
        identity = gen.story_identity(story)
        title = gen.clean(story.get("title"))
        expected.append({"articleId": identity, "title": title, "contentSha256": digest})
        if gen.reusable_entry(previous, story, digest) or gen.can_reuse_legacy_lead(previous, latest_raw, story, lead_title):
            reusable += 1
        else:
            missing.append((story, digest))

    selected = [item for position, item in enumerate(missing) if position % SHARD_COUNT == SHARD_INDEX]
    print(
        f"COSYVOICE_SHARD_PLAN shard={SHARD_INDEX}/{SHARD_COUNT} stories={len(stories)} "
        f"reusable={reusable} missing={len(missing)} selected={len(selected)} source_set_sha256={source_set_sha}",
        flush=True,
    )

    entries = {}
    if selected:
        model, prompt = gen.setup_model()
        audio_dir = OUT_DIR / "audio" / f"shard-{SHARD_INDEX}"
        for number, (story, digest) in enumerate(selected, start=1):
            identity = gen.story_identity(story)
            title = gen.clean(story.get("title"))
            final_path = gen.target_path(story, digest)
            artifact_path = audio_dir / final_path.name
            print(f"=== shard {SHARD_INDEX} article {number}/{len(selected)}: {title} ===", flush=True)
            meta = gen.synthesize_story(model, prompt, story, artifact_path)
            entries[identity] = {
                "articleId": identity,
                "title": title,
                "audio": final_path.as_posix(),
                "artifactAudio": artifact_path.as_posix(),
                "wavEncoding": "PCM16",
                "contentSha256": digest,
                **meta,
            }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "shardIndex": SHARD_INDEX,
        "shardCount": SHARD_COUNT,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "engine": "ASLP-lab/Cosyvoice2-Yue",
        "voice": "F01 female reference",
        "language": "yue-HK",
        "date": latest.get("date"),
        "leadId": lead_id,
        "leadTitle": lead_title,
        "sourceSha256": hashlib.sha256(latest_raw).hexdigest(),
        "sourceSetSha256": source_set_sha,
        "sourceFiles": loaded_paths,
        "collectedStoryCount": len(stories),
        "expectedArticles": expected,
        "entries": entries,
    }
    out = OUT_DIR / f"shard-{SHARD_INDEX}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"COSYVOICE_SHARD_PASS shard={SHARD_INDEX} generated={len(entries)} output={out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
