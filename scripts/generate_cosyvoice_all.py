#!/usr/bin/env python3
import hashlib
import json
import os
import re
import shutil
import sys
import time
import urllib.request
import wave
from datetime import datetime, timezone
from pathlib import Path

import torch
import torchaudio

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import generate_cosyvoice_lead as base

ROOT = Path(".")
LATEST = Path(os.environ.get("COSY_LATEST_JSON", "data/latest.json"))
MANIFEST = Path(os.environ.get("COSY_MANIFEST_JSON", "data/tts-manifest.json"))
AUDIO_DIR = Path(os.environ.get("COSY_AUDIO_DIR", "assets/audio/cosyvoice/articles"))
LEAD_ALIAS = Path(os.environ.get("COSY_OUTPUT_WAV", "assets/audio/cosyvoice/latest-lead.wav"))
ARTICLE_TEXT_LIMIT = int(os.environ.get("COSY_ARTICLE_MAX_TEXT_CHARS", "340"))
MAX_ARTICLES = int(os.environ.get("COSY_MAX_ARTICLES", "120"))
MAX_NEW_ARTICLES = int(os.environ.get("COSY_MAX_NEW_ARTICLES", "0"))

STORY_FIELDS = ("title", "dek", "summary", "body", "context", "background", "why", "whyImportant", "watchNext", "nextStep")


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def safe_id(value):
    raw = clean(value).lower()
    raw = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-._")
    return (raw[:72] or "story")


def story_identity(story):
    explicit = story.get("id") or story.get("articleId") or story.get("storyId")
    if explicit:
        return safe_id(explicit)
    return "story-" + hashlib.sha256(clean(story.get("title")).encode("utf-8")).hexdigest()[:16]


def speech_source_text(story):
    values = []
    seen = set()
    for key in STORY_FIELDS:
        value = clean(story.get(key))
        if not value or value in seen:
            continue
        seen.add(value)
        values.append(value)
    return "\n".join(values)


def content_sha(story):
    normalized = base.normalize_for_tts(speech_source_text(story))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def looks_like_story(obj):
    if not isinstance(obj, dict) or not clean(obj.get("title")):
        return False
    return any(clean(obj.get(key)) for key in ("dek", "summary", "body", "context", "background", "why", "whyImportant", "watchNext", "nextStep"))


def walk_stories(node):
    if isinstance(node, dict):
        if looks_like_story(node):
            yield node
        for value in node.values():
            yield from walk_stories(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_stories(value)


def load_json(path):
    if not path.exists():
        return None, b""
    raw = path.read_bytes()
    return json.loads(raw.decode("utf-8")), raw


def source_paths(date_value):
    paths = [
        Path("data/latest.json"),
        Path("data/desk-latest.json"),
        Path("data/live.json"),
        Path("data/stocks-latest.json"),
    ]
    if date_value:
        paths.extend([
            Path(f"data/topic-more/{date_value}.json"),
            Path(f"data/editorial-overrides/{date_value}.json"),
        ])
    return paths


def collect_current_stories():
    latest, latest_raw = load_json(LATEST)
    if not latest:
        raise RuntimeError("data/latest.json is missing or empty")
    date_value = latest.get("date")
    selected = {}
    order = []
    source_hash = hashlib.sha256()
    loaded_paths = []

    for path in source_paths(date_value):
        data, raw = load_json(path)
        if data is None:
            continue
        loaded_paths.append(path.as_posix())
        source_hash.update(path.as_posix().encode("utf-8") + b"\0" + raw + b"\0")
        for story in walk_stories(data):
            title_key = clean(story.get("title"))
            if not title_key:
                continue
            score = len(speech_source_text(story))
            if title_key not in selected:
                selected[title_key] = (story, score)
                order.append(title_key)
            elif score > selected[title_key][1]:
                selected[title_key] = (story, score)

    stories = [selected[key][0] for key in order]
    if len(stories) > MAX_ARTICLES:
        raise RuntimeError(f"refusing to synthesize {len(stories)} stories; MAX_ARTICLES={MAX_ARTICLES}")

    lead_id = latest.get("leadId")
    latest_articles = latest.get("articles") or []
    lead_story = next((item for item in latest_articles if item.get("id") == lead_id), None)
    if lead_story is None and latest_articles:
        lead_story = latest_articles[0]
        lead_id = lead_story.get("id")
    if not lead_story:
        raise RuntimeError("latest.json has no lead story")
    lead_title = clean(lead_story.get("title"))

    # Put the lead first while preserving the source order of every other story.
    stories.sort(key=lambda item: 0 if clean(item.get("title")) == lead_title else 1)
    return latest, latest_raw, stories, lead_id, lead_title, source_hash.hexdigest(), loaded_paths


def add_field_segments(target, role, value, budget, pause):
    text = base.normalize_for_tts(value)
    if not text or budget <= 0:
        return budget
    if len(text) > budget:
        text = text[:budget]
    base.add_role_segments(target, role, text, pause)
    return budget - len(text)


def build_article_segments(story):
    segments = []
    budget = ARTICLE_TEXT_LIMIT
    seen = set()

    def add(role, value, pause):
        nonlocal budget
        raw = clean(value)
        if not raw or raw in seen or budget <= 0:
            return
        seen.add(raw)
        budget = add_field_segments(segments, role, raw, budget, pause)

    add("title", story.get("title"), base.TITLE_PAUSE_SECONDS)
    add("dek", story.get("dek"), base.DEK_PAUSE_SECONDS)
    add("summary", story.get("summary"), base.DEK_PAUSE_SECONDS)
    paragraphs = [clean(p) for p in re.split(r"\n\s*\n", str(story.get("body") or "")) if clean(p)]
    for paragraph in paragraphs[:2]:
        add("body", paragraph, base.BODY_PAUSE_SECONDS)
    add("context", story.get("context") or story.get("background"), base.BODY_PAUSE_SECONDS)
    add("why", story.get("why") or story.get("whyImportant"), base.BODY_PAUSE_SECONDS)
    add("next", story.get("watchNext") or story.get("nextStep"), base.BODY_PAUSE_SECONDS)

    chars = sum(len(item["text"]) for item in segments)
    if not segments or chars < 8:
        raise RuntimeError(f"story text too short for TTS: {story.get('title')!r}")
    return segments


def wav_metadata(path):
    with wave.open(str(path), "rb") as handle:
        if handle.getsampwidth() != 2:
            raise RuntimeError(f"not PCM16: {path}")
        frames = handle.getnframes()
        rate = handle.getframerate()
        duration = frames / float(rate)
    return duration, path.stat().st_size


def load_previous_manifest():
    if not MANIFEST.exists():
        return {}
    try:
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if data.get("engine") != "ASLP-lab/Cosyvoice2-Yue" or data.get("voice") != "F01 female reference":
            return {}
        return data
    except Exception:
        return {}


def previous_entry_for_title(previous, title):
    for entry in (previous.get("articles") or {}).values():
        if clean(entry.get("title")) == title:
            return entry
    return None


def target_path(story, digest):
    return AUDIO_DIR / f"{story_identity(story)}-{digest[:12]}.wav"


def reusable_entry(previous, story, digest):
    old = previous_entry_for_title(previous, clean(story.get("title")))
    if not old or old.get("contentSha256") != digest:
        return None
    path = Path(str(old.get("audio") or ""))
    if not path.exists() or path.stat().st_size < 50000:
        return None
    duration, size = wav_metadata(path)
    if duration <= 2:
        return None
    entry = dict(old)
    entry["durationSeconds"] = round(duration, 3)
    entry["bytes"] = size
    return entry


def can_reuse_legacy_lead(previous, latest_raw, story, lead_title):
    if clean(story.get("title")) != lead_title:
        return False
    old = previous_entry_for_title(previous, lead_title)
    if not old:
        return False
    if previous.get("sourceSha256") != hashlib.sha256(latest_raw).hexdigest():
        return False
    path = Path(str(old.get("audio") or ""))
    return path.exists() and path.stat().st_size > 50000


def setup_model():
    if not base.CODE_ROOT.exists():
        raise RuntimeError(f"WenetSpeech-Yue code not found: {base.CODE_ROOT}")
    base.ensure_model()
    sys.path.insert(0, str(base.CODE_ROOT))
    sys.path.insert(0, str(base.CODE_ROOT / "third_party" / "Matcha-TTS"))
    base.install_offline_wetext_stub()
    from cosyvoice.cli.cosyvoice import CosyVoice2
    from cosyvoice.utils.file_utils import load_wav

    ref = Path("/tmp/F01_female.wav")
    urllib.request.urlretrieve(base.F01_URL, ref)
    if ref.stat().st_size < 10000:
        raise RuntimeError("F01 female reference download is too small")
    print("Loading CosyVoice2-Yue F01 runtime on CPU...", flush=True)
    t0 = time.time()
    model = CosyVoice2(str(base.MODEL_DIR), load_jit=False, load_trt=False, load_vllm=False, fp16=False)
    prompt = load_wav(str(ref), 16000)
    print(f"Model loaded in {time.time()-t0:.1f}s sample_rate={model.sample_rate}", flush=True)
    return model, prompt


def synthesize_story(model, prompt, story, path):
    segments = build_article_segments(story)
    speech_chars = sum(len(item["text"]) for item in segments)
    audio_parts = []
    for index, item in enumerate(segments):
        audio = base.synthesize_segment(model, prompt, item, index)
        audio_parts.append(audio)
        pause_samples = int(round(model.sample_rate * item["pause"]))
        if pause_samples > 0:
            audio_parts.append(torch.zeros((1, pause_samples), dtype=audio.dtype))
    speech = torch.cat(audio_parts, dim=1).clamp(-1.0, 1.0)
    duration = speech.shape[1] / model.sample_rate
    max_reasonable = max(40.0, speech_chars * 0.45)
    if duration > max_reasonable:
        raise RuntimeError(
            f"audio suspiciously long; possible prompt leakage: {story.get('title')} duration={duration:.3f}s limit={max_reasonable:.3f}s"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(path), speech, model.sample_rate, encoding="PCM_S", bits_per_sample=16, backend="soundfile")
    duration, size = wav_metadata(path)
    if duration <= 2 or size < 50000:
        raise RuntimeError(f"invalid generated WAV for {story.get('title')}: duration={duration:.3f}s bytes={size}")
    return {
        "segmentCount": len(segments),
        "speechTextChars": speech_chars,
        "durationSeconds": round(duration, 3),
        "bytes": size,
    }


def main():
    print("=== COSYVOICE2-YUE F01 ALL-NEWS GENERATOR ===", flush=True)
    latest, latest_raw, stories, lead_id, lead_title, source_set_sha, loaded_paths = collect_current_stories()
    previous = load_previous_manifest()
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)

    plan = []
    entries = {}
    reused = 0
    generated = 0

    for story in stories:
        digest = content_sha(story)
        title = clean(story.get("title"))
        path = target_path(story, digest)
        old = reusable_entry(previous, story, digest)
        if old:
            entries[story_identity(story)] = old
            reused += 1
            continue
        if can_reuse_legacy_lead(previous, latest_raw, story, lead_title):
            legacy = Path(previous_entry_for_title(previous, lead_title)["audio"])
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(legacy, path)
            duration, size = wav_metadata(path)
            entries[story_identity(story)] = {
                "articleId": story_identity(story),
                "title": title,
                "audio": path.as_posix(),
                "wavEncoding": "PCM16",
                "contentSha256": digest,
                "segmentCount": int(previous_entry_for_title(previous, lead_title).get("segmentCount") or 0),
                "speechTextChars": int(previous_entry_for_title(previous, lead_title).get("speechTextChars") or 0),
                "durationSeconds": round(duration, 3),
                "bytes": size,
            }
            reused += 1
            continue
        plan.append((story, digest, path))

    if MAX_NEW_ARTICLES > 0 and len(plan) > MAX_NEW_ARTICLES:
        print(f"TEST LIMIT: generating first {MAX_NEW_ARTICLES} of {len(plan)} missing stories", flush=True)
        plan = plan[:MAX_NEW_ARTICLES]

    print(f"stories={len(stories)} reused={reused} missing_to_generate={len(plan)} source_set_sha256={source_set_sha}", flush=True)
    print(f"sources={loaded_paths}", flush=True)

    model = prompt = None
    if plan:
        model, prompt = setup_model()
        for number, (story, digest, path) in enumerate(plan, start=1):
            title = clean(story.get("title"))
            print(f"=== article {number}/{len(plan)}: {title} ===", flush=True)
            meta = synthesize_story(model, prompt, story, path)
            entries[story_identity(story)] = {
                "articleId": story_identity(story),
                "title": title,
                "audio": path.as_posix(),
                "wavEncoding": "PCM16",
                "contentSha256": digest,
                **meta,
            }
            generated += 1

    # In production (no test limit), every collected story must have F01 audio.
    if MAX_NEW_ARTICLES == 0 and len(entries) != len(stories):
        missing = [clean(story.get("title")) for story in stories if story_identity(story) not in entries]
        raise RuntimeError(f"all-news F01 coverage incomplete: {len(entries)}/{len(stories)} missing={missing[:5]}")

    lead_entry = next((entry for entry in entries.values() if clean(entry.get("title")) == lead_title), None)
    if not lead_entry:
        raise RuntimeError("lead story has no F01 entry")
    lead_path = Path(lead_entry["audio"])
    LEAD_ALIAS.parent.mkdir(parents=True, exist_ok=True)
    if lead_path.resolve() != LEAD_ALIAS.resolve():
        shutil.copyfile(lead_path, LEAD_ALIAS)

    manifest = {
        "version": 2,
        "engine": "ASLP-lab/Cosyvoice2-Yue",
        "voice": "F01 female reference",
        "language": "yue-HK",
        "pronunciationPolicy": "cantonese-only",
        "instructionPolicy": "short-no-leak",
        "coveragePolicy": "all-current-news-f01-only",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "multi-source-current-site",
        "sourceSha256": hashlib.sha256(latest_raw).hexdigest(),
        "sourceSetSha256": source_set_sha,
        "sourceFiles": loaded_paths,
        "date": latest.get("date"),
        "leadId": lead_id,
        "leadTitle": lead_title,
        "articleCount": len(entries),
        "collectedStoryCount": len(stories),
        "generatedArticleCount": generated,
        "reusedArticleCount": reused,
        "articles": entries,
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lead_duration, lead_size = wav_metadata(LEAD_ALIAS)
    print(
        f"COSYVOICE_ALL_NEWS_PASS articles={len(entries)}/{len(stories)} generated={generated} reused={reused} "
        f"lead_duration={lead_duration:.3f}s lead_bytes={lead_size}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
