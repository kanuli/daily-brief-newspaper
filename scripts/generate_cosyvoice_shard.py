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
ONE_ARTICLE = os.environ.get("COSY_SHARD_ONE_ARTICLE", "0").strip().lower() in {"1", "true", "yes", "on"}
STABLE_SLOT = os.environ.get("COSY_SHARD_STABLE_SLOT", "0").strip().lower() in {"1", "true", "yes", "on"}
OUT_DIR = Path(os.environ.get("COSY_SHARD_OUT_DIR", "artifacts/cosyvoice-shards"))


def priority_map(lead_title):
    """Prioritise the current lead, then hourly Live/Stock stories, then the rest."""
    ranking = {}
    next_rank = 0

    def add_title(title):
        nonlocal next_rank
        title = gen.clean(title)
        if title and title not in ranking:
            ranking[title] = next_rank
            next_rank += 1

    add_title(lead_title)
    for path in (
        Path("data/live.json"),
        Path("data/stocks-latest.json"),
        Path("data/latest.json"),
        Path("data/desk-latest.json"),
    ):
        data, _ = gen.load_json(path)
        if data is None:
            continue
        for story in gen.walk_stories(data):
            add_title(story.get("title"))
    return ranking


def stable_slot(story):
    identity = gen.story_identity(story)
    digest = hashlib.sha256(identity.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % SHARD_COUNT


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

    priorities = priority_map(lead_title)
    missing.sort(key=lambda item: (priorities.get(gen.clean(item[0].get("title")), 10**9), gen.clean(item[0].get("title"))))

    if ONE_ARTICLE and STABLE_SLOT:
        assigned = [item for item in missing if stable_slot(item[0]) == SHARD_INDEX]
        selected = assigned[:1]
        selection_mode = "one-article-stable-worker-lane"
    elif ONE_ARTICLE:
        selected = [missing[SHARD_INDEX]] if SHARD_INDEX < len(missing) else []
        selection_mode = "one-article-fast-lane"
    else:
        selected = [item for position, item in enumerate(missing) if position % SHARD_COUNT == SHARD_INDEX]
        selection_mode = "distributed-backfill"

    print(
        f"COSYVOICE_SHARD_PLAN shard={SHARD_INDEX}/{SHARD_COUNT} mode={selection_mode} stories={len(stories)} "
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
        "version": 3,
        "shardIndex": SHARD_INDEX,
        "shardCount": SHARD_COUNT,
        "selectionMode": selection_mode,
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
    print(f"COSYVOICE_SHARD_PASS shard={SHARD_INDEX} mode={selection_mode} generated={len(entries)} output={out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
