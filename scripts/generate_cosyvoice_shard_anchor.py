#!/usr/bin/env python3
"""Generate one F01 shard using the user-approved golden news-anchor voice.

Policy goals:
- Use the Nvidia article voice explicitly approved by the user as the canonical
  F01 news-anchor reference.
- Keep reference-only Cantonese synthesis; no textual instruction can leak.
- Reset the stochastic sampler for every segment so speaker age/timbre cannot
  wander between the opening and later segments.
- Use only gentle tempo correction; never push a segment by the old +/-12%.
- Never reuse audio produced by an older prosody policy.
"""
import re
import sys
import time
import urllib.request
from pathlib import Path

import torch
import torchaudio

import generate_cosyvoice_lead as voice_base
import generate_cosyvoice_shard as legacy

POLICY = "f01-news-anchor-v4-golden-nvidia"
REFERENCE_POLICY = "user-approved-nvidia-anchor-v1"
GOLDEN_REFERENCE_ASSET = "ai-nvidia-server-price-0800-79489f0afc38.wav"
GOLDEN_REFERENCE_URL = (
    "https://github.com/kanuli/daily-brief-newspaper/releases/download/"
    "f01-voice-cache/" + GOLDEN_REFERENCE_ASSET
)
REFERENCE_START_SECONDS = 10.0
REFERENCE_DURATION_SECONDS = 10.0
VOICE_RANDOM_SEED = 20260823
SEGMENT_CHARS = 72
TARGET_CHARS_PER_SECOND = 4.0
MIN_TEMPO = 0.96
MAX_TEMPO = 1.04

_ORIGINAL_SEGMENT_SYNTH = voice_base.synthesize_segment


def _setup_model_golden():
    if not voice_base.CODE_ROOT.exists():
        raise RuntimeError(f"WenetSpeech-Yue code not found: {voice_base.CODE_ROOT}")
    voice_base.ensure_model()
    sys.path.insert(0, str(voice_base.CODE_ROOT))
    sys.path.insert(0, str(voice_base.CODE_ROOT / "third_party" / "Matcha-TTS"))
    voice_base.install_offline_wetext_stub()
    from cosyvoice.cli.cosyvoice import CosyVoice2
    from cosyvoice.utils.file_utils import load_wav

    ref = Path("/tmp/F01_golden_nvidia.wav")
    urllib.request.urlretrieve(GOLDEN_REFERENCE_URL, ref)
    if ref.stat().st_size < 50000:
        raise RuntimeError("golden F01 reference download is too small")

    print("Loading CosyVoice2-Yue golden F01 runtime on CPU...", flush=True)
    t0 = time.time()
    model = CosyVoice2(
        str(voice_base.MODEL_DIR),
        load_jit=False,
        load_trt=False,
        load_vllm=False,
        fp16=False,
    )
    prompt = load_wav(str(ref), 16000)
    if prompt.ndim != 2 or prompt.shape[1] < 16000 * 4:
        raise RuntimeError("golden F01 reference audio is too short")
    start = int(round(REFERENCE_START_SECONDS * 16000))
    length = int(round(REFERENCE_DURATION_SECONDS * 16000))
    if start + length > prompt.shape[1]:
        start = max(0, prompt.shape[1] - length)
    prompt = prompt[:, start:start + length]
    if prompt.shape[1] < 16000 * 4:
        raise RuntimeError("golden F01 reference crop is too short")
    print(
        f"Golden reference={GOLDEN_REFERENCE_ASSET} "
        f"start={start/16000:.2f}s duration={prompt.shape[1]/16000:.2f}s "
        f"loaded_in={time.time()-t0:.1f}s",
        flush=True,
    )
    return model, prompt


def _stable_segment_synth(model, prompt, item, index):
    # CosyVoice cross-lingual generation contains stochastic sampling. Resetting
    # to one fixed seed for every segment greatly reduces speaker/timbre drift.
    torch.manual_seed(VOICE_RANDOM_SEED)
    return _ORIGINAL_SEGMENT_SYNTH(model, prompt, item, index)


def _policy_remote_reusable(previous, story, digest):
    old = legacy.gen.previous_entry_for_title(previous, legacy.gen.clean(story.get("title")))
    if not old or old.get("contentSha256") != digest or old.get("prosodyPolicy") != POLICY:
        return False
    if old.get("referencePolicy") != REFERENCE_POLICY:
        return False
    audio = str(old.get("audio") or "")
    if not audio.startswith(("https://", "http://")):
        return False
    try:
        return int(old.get("bytes") or 0) >= 50000 and float(old.get("durationSeconds") or 0) > 2
    except (TypeError, ValueError):
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

    pieces = voice_base.split_for_tts(script, max_chars=SEGMENT_CHARS)
    return [
        {
            "role": "news",
            "text": piece,
            "pause": 0.26 if index < len(pieces) - 1 else 0.40,
        }
        for index, piece in enumerate(pieces)
    ]


def _speech_units(text):
    text = str(text or "")
    cjk = len(re.findall(r"[\u3400-\u9fff]", text))
    latin_words = len(re.findall(r"[A-Za-z]+", text))
    numbers = len(re.findall(r"\d+", text))
    return max(1, cjk + latin_words * 2 + numbers)


def _stabilize_tempo(audio, text, sample_rate):
    duration = audio.shape[1] / float(sample_rate)
    units = _speech_units(text)
    target_duration = max(1.2, units / TARGET_CHARS_PER_SECOND)
    factor = duration / target_duration
    factor = max(MIN_TEMPO, min(MAX_TEMPO, factor))
    if 0.985 <= factor <= 1.015:
        return audio, 1.0
    try:
        adjusted, _ = torchaudio.sox_effects.apply_effects_tensor(
            audio,
            sample_rate,
            [["tempo", "-s", f"{factor:.4f}"]],
        )
        if adjusted.numel() > 0:
            return adjusted, factor
    except Exception as exc:
        print(f"tempo-normalization skipped: {exc}", flush=True)
    return audio, 1.0


def _policy_synth(model, prompt, story, path):
    segments = _anchor_script_segments(story)
    speech_chars = sum(len(item["text"]) for item in segments)
    audio_parts = []
    applied = []
    for index, item in enumerate(segments):
        audio = _stable_segment_synth(model, prompt, item, index)
        audio, factor = _stabilize_tempo(audio, item["text"], model.sample_rate)
        applied.append(round(factor, 4))
        audio_parts.append(audio)
        pause_samples = int(round(model.sample_rate * item["pause"]))
        if pause_samples > 0:
            audio_parts.append(torch.zeros((1, pause_samples), dtype=audio.dtype))

    speech = torch.cat(audio_parts, dim=1).clamp(-1.0, 1.0)
    duration = speech.shape[1] / model.sample_rate
    max_reasonable = max(40.0, speech_chars * 0.60)
    if duration > max_reasonable:
        raise RuntimeError(
            f"audio suspiciously long: {story.get('title')} duration={duration:.3f}s limit={max_reasonable:.3f}s"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(path), speech, model.sample_rate, encoding="PCM_S", bits_per_sample=16, backend="soundfile")
    duration, size = legacy.gen.wav_metadata(path)
    if duration <= 2 or size < 50000:
        raise RuntimeError(f"invalid generated WAV for {story.get('title')}: duration={duration:.3f}s bytes={size}")
    return {
        "segmentCount": len(segments),
        "speechTextChars": speech_chars,
        "durationSeconds": round(duration, 3),
        "bytes": size,
        "prosodyPolicy": POLICY,
        "referencePolicy": REFERENCE_POLICY,
        "referenceAsset": GOLDEN_REFERENCE_ASSET,
        "randomSeed": VOICE_RANDOM_SEED,
        "inferenceMode": voice_base.VOICE_INFERENCE_MODE,
        "speed": voice_base.VOICE_SPEED,
        "instructionPolicy": "none-reference-only",
        "tempoTargetCharsPerSecond": TARGET_CHARS_PER_SECOND,
        "tempoFactors": applied,
    }


legacy.remote_reusable = _policy_remote_reusable
legacy.gen.setup_model = _setup_model_golden
legacy.gen.build_article_segments = _anchor_script_segments
legacy.gen.synthesize_story = _policy_synth
legacy.gen.can_reuse_legacy_lead = lambda *args, **kwargs: False

if __name__ == "__main__":
    raise SystemExit(legacy.main())
