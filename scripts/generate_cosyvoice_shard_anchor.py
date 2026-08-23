#!/usr/bin/env python3
"""Generate one production F01 shard with the approved news-anchor reference."""
import re
import sys
import time
import urllib.request
from pathlib import Path

import torch
import torchaudio

import cosyvoice_policy as voice_policy
import generate_cosyvoice_lead as voice_base
import generate_cosyvoice_shard as legacy
import tts_hktrad_v2 as hktrad

POLICY = voice_policy.POLICY
REFERENCE_POLICY = voice_policy.REFERENCE_POLICY
GOLDEN_REFERENCE_ASSET = voice_policy.REFERENCE_ASSET
GOLDEN_REFERENCE_URL = (
    "https://github.com/kanuli/daily-brief-newspaper/releases/download/"
    "f01-voice-cache/" + GOLDEN_REFERENCE_ASSET
)
REFERENCE_START_SECONDS = voice_policy.REFERENCE_START_SECONDS
REFERENCE_DURATION_SECONDS = voice_policy.REFERENCE_DURATION_SECONDS
VOICE_RANDOM_SEED = 20260823
# CosyVoice's normal Chinese frontend deliberately works around an ~80-token
# ceiling. To keep one model session per article without sending ~260 tokens
# as one oversized tensor, stream conservative text chunks through CosyVoice2's
# native inference_bistream path. The chunks are input transport only: they do
# NOT create new cross-lingual inference sessions and therefore do not reset the
# voice/language anchor halfway through an article.
STREAM_INPUT_CHARS = 48
TARGET_CHARS_PER_SECOND = 4.0
MIN_TEMPO = 0.96
MAX_TEMPO = 1.04

_ORIGINAL_NORMALIZE = voice_base.normalize_for_tts


def _localized_normalize(value):
    return hktrad.localize(_ORIGINAL_NORMALIZE(value))


voice_base.normalize_for_tts = _localized_normalize


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


def _policy_remote_reusable(previous, story, digest):
    old = legacy.gen.previous_entry_for_title(previous, legacy.gen.clean(story.get("title")))
    if not old or old.get("contentSha256") != digest or old.get("prosodyPolicy") != POLICY:
        return False
    if old.get("referencePolicy") != REFERENCE_POLICY:
        return False
    if float(old.get("referenceDurationSeconds") or 0) != REFERENCE_DURATION_SECONDS:
        return False
    if old.get("initialConditioningPolicy") != voice_policy.INITIAL_CONDITIONING_POLICY:
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

    residual = hktrad.residual_latin_tokens(script)
    if residual:
        raise RuntimeError(
            f"TTS residual Latin gate blocked {story.get('id') or story.get('title')}: "
            + ", ".join(residual)
        )

    return [{"role": "news", "text": script, "pause": 0.40}]


def _stream_input_pieces(text):
    pieces = voice_base.split_for_tts(text, max_chars=STREAM_INPUT_CHARS)
    pieces = [piece for piece in pieces if piece]
    if not pieces:
        raise RuntimeError("streaming TTS input produced no text chunks")
    return pieces


def _stable_segment_synth(model, prompt, item, index):
    text = item["text"]
    pieces = _stream_input_pieces(text)
    torch.manual_seed(VOICE_RANDOM_SEED)
    print(
        f"segment={index} role={item['role']} chars={len(text)} "
        f"mode={voice_base.VOICE_INFERENCE_MODE} input=single-session-bistream "
        f"chunks={len(pieces)} speed={voice_base.VOICE_SPEED} "
        f"reference_seconds={REFERENCE_DURATION_SECONDS}",
        flush=True,
    )

    def token_text_stream():
        for chunk_index, piece in enumerate(pieces):
            print(
                f"segment={index} input_chunk={chunk_index}/{len(pieces)} chars={len(piece)} text={piece}",
                flush=True,
            )
            yield piece

    audio_chunks = []
    with torch.inference_mode():
        for chunk_index, result in enumerate(
            model.inference_cross_lingual(
                token_text_stream(),
                prompt,
                stream=False,
                speed=voice_base.VOICE_SPEED,
                text_frontend=False,
            )
        ):
            speech = result["tts_speech"].detach().cpu()
            if speech.numel() == 0:
                continue
            print(f"segment={index} output_chunk={chunk_index} shape={tuple(speech.shape)}", flush=True)
            audio_chunks.append(speech)

    if not audio_chunks:
        raise RuntimeError(f"CosyVoice2-Yue returned zero audio for article session {index}")
    return torch.cat(audio_chunks, dim=1), len(pieces)


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
    input_chunk_counts = []
    for index, item in enumerate(segments):
        audio, input_chunks = _stable_segment_synth(model, prompt, item, index)
        input_chunk_counts.append(input_chunks)
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
        "referenceStartSeconds": REFERENCE_START_SECONDS,
        "referenceDurationSeconds": REFERENCE_DURATION_SECONDS,
        "initialConditioningPolicy": voice_policy.INITIAL_CONDITIONING_POLICY,
        "randomSeed": VOICE_RANDOM_SEED,
        "inferenceMode": voice_base.VOICE_INFERENCE_MODE,
        "speed": voice_base.VOICE_SPEED,
        "instructionPolicy": "none-reference-only",
        "languageGate": voice_policy.LANGUAGE_GATE,
        "segmentPolicy": voice_policy.SEGMENT_POLICY,
        "inputTransport": "native-bistream-single-session",
        "streamInputChunkChars": STREAM_INPUT_CHARS,
        "streamInputChunkCounts": input_chunk_counts,
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
