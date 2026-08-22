#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import generate_cosyvoice_all as gen


def main():
    if len(sys.argv) != 2:
        raise RuntimeError("usage: promote_cosyvoice_prepublish.py <prepublish-worktree>")
    root = Path(sys.argv[1])
    manifest_path = root / "data/prepublish-tts-manifest.json"
    if not manifest_path.is_file():
        print("COSYVOICE_PREPUBLISH_PROMOTE_NOOP no prepublish manifest", flush=True)
        return 0
    pre = json.loads(manifest_path.read_text(encoding="utf-8"))
    if pre.get("engine") != "ASLP-lab/Cosyvoice2-Yue" or pre.get("voice") != "F01 female reference" or pre.get("language") != "yue-HK":
        raise RuntimeError("prepublish manifest is not approved F01 yue-HK")

    _, _, stories, _, _, _, _ = gen.collect_current_stories()
    current = {}
    current_by_title = {}
    for story in stories:
        article_id = gen.story_identity(story)
        title = gen.clean(story.get("title"))
        digest = gen.content_sha(story)
        item = (story, article_id, title, digest)
        current[article_id] = item
        current_by_title[title] = item

    candidates = []
    for pre_id, entry in (pre.get("articles") or {}).items():
        title = gen.clean(entry.get("title"))
        wanted = current.get(pre_id) or current_by_title.get(title)
        if not wanted:
            continue
        _, article_id, current_title, digest = wanted
        if entry.get("contentSha256") != digest:
            continue
        rel_audio = Path(str(entry.get("audio") or ""))
        source_audio = root / rel_audio
        if not source_audio.is_file() or source_audio.stat().st_size < 50000:
            continue
        candidates.append((article_id, current_title, digest, entry, source_audio))

    promoted = 0
    for article_id, title, digest, entry, source_audio in candidates:
        payload_entry = dict(entry)
        payload_entry.update({
            "articleId": article_id,
            "title": title,
            "contentSha256": digest,
            "artifactAudio": str(source_audio),
        })
        shard = {
            "version": 1,
            "engine": "ASLP-lab/Cosyvoice2-Yue",
            "voice": "F01 female reference",
            "language": "yue-HK",
            "entries": {article_id: payload_entry},
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", encoding="utf-8", delete=False) as handle:
            json.dump(shard, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            shard_path = handle.name
        subprocess.run([sys.executable, "scripts/publish_cosyvoice_article.py", shard_path], check=True)
        promoted += 1

    print(f"COSYVOICE_PREPUBLISH_PROMOTE_PASS matched={len(candidates)} promoted={promoted}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
