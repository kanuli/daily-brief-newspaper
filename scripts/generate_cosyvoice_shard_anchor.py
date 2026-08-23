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
STREAM_INPUT_CHARS = 48

_ORIGINAL_NORMALIZE = voice_base.normalize_for_tts


def _localized_normalize(value):
    return hktrad.localize(_ORIGINAL_NORMALIZE(value))


voice_base.normalize_for_tts = _localized_normalize


_REPORTING_VERBS = ("表示", "指出", "宣布", "稱", "認為", "警告", "強調", "證實")
_CONNECTORS = ("同時", "另外", "其後", "不過", "然而", "而", "但", "以及", "並")
_KEY_DATA_RE = re.compile(
    r"([零一二三四五六七八九十百千萬億兆點]+(?:百分比|美元|港元|英鎊|歐元|日圓|公里|納米|級))"
    r"(?=[^，。！？；：])"
)


def _semantic_sentence_pauses(sentence):
    """Add punctuation-only anchor pauses without adding spoken instructions."""
    text = str(sentence or "").strip()
    if len(text) < 8:
        return text

    # Long introductory modifiers: breathe after a complete time/location/
    # circumstance phrase instead of rushing directly into the main clause.
    if "，" not in text[:28]:
        intro = re.match(
            r"((?:在|截至|隨著|由於|根據|按照|受)[^，。！？；]{7,26}?(?:後|前|時|期間|之際|下|中|內|方面))",
            text,
        )
        if intro:
            cut = intro.end()
            text = text[:cut] + "，" + text[cut:]

    # Long subject phrases get one micro-pause before the reporting verb. For a
    # shorter subject, pause after the reporting verb before a long object/clause.
    verb_match = re.search("|".join(_REPORTING_VERBS), text)
    if verb_match:
        before = text[:verb_match.start()]
        after = text[verb_match.end():]
        if len(before) >= 12 and not re.search(r"[，；：]", before[-14:]):
            text = text[:verb_match.start()] + "，" + text[verb_match.start():]
        elif len(after) >= 12 and after[:1] not in "，。！？；：":
            pos = verb_match.end()
            text = text[:pos] + "，" + text[pos:]

    # Key numerical data should land cleanly. Add a micro-pause after the full
    # number+unit phrase, never split the number from its unit.
    text = _KEY_DATA_RE.sub(r"\1，", text)

    # A long clause with very little punctuation gets one additional semantic
    # break at a natural connector near the middle. This reduces cognitive load
    # without turning every phrase into a separate TTS inference session.
    if len(text) >= 42 and text.count("，") < 2:
        for connector in _CONNECTORS:
            idx = text.find(connector, 16)
            if 16 <= idx <= len(text) - 10 and text[idx - 1:idx] not in "，；：。！？":
                text = text[:idx] + "，" + text[idx:]
                break

    text = re.sub(r"，{2,}", "，", text)
    text = re.sub(r"；{2,}", "；", text)
    return text


def _apply_semantic_pauses(text):
    out = str(text or "")
    out = out.replace(",", "，").replace(";", "；")
    # Preserve sentence-ending punctuation while applying the rules sentence by
    # sentence so a full stop remains a full beat and commas remain micro-pauses.
    parts = re.split(r"([。！？；])", out)
    rebuilt = []
    for idx in range(0, len(parts), 2):
        sentence = parts[idx]
        mark = parts[idx + 1] if idx + 1 < len(parts) else ""
        if sentence:
            rebuilt.append(_semantic_sentence_pauses(sentence))
        if mark:
            rebuilt.append(mark)
    return "".join(rebuilt)


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
    if old.get("pacingPolicy") != voice_policy.PACING_POLICY:
        return False
    if old.get("tempoPolicy") != voice_policy.TEMPO_POLICY:
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
        text = _apply_semantic_pauses(voice_base.normalize_for_tts(raw))
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
        f"mode={voice_policy.INFERENCE_MODE} input=single-session-bistream "
        f"chunks={len(pieces)} speed={voice_policy.VOICE_SPEED} "
        f"reference_seconds={REFERENCE_DURATION_SECONDS} pacing={voice_policy.PACING_POLICY}",
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
                speed=voice_policy.VOICE_SPEED,
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


def _policy_synth(model, prompt, story, path):
    segments = _anchor_script_segments(story)
    speech_chars = sum(len(item["text"]) for item in segments)
    audio_parts = []
    input_chunk_counts = []
    for index, item in enumerate(segments):
        audio, input_chunks = _stable_segment_synth(model, prompt, item, index)
        input_chunk_counts.append(input_chunks)
        audio_parts.append(audio)
        pause_samples = int(round(model.sample_rate * item["pause"]))
        if pause_samples > 0:
            audio_parts.append(torch.zeros((1, pause_samples), dtype=audio.dtype))

    # Do not post-stretch the waveform. Speaker age/timbre is more important
    # than forcing every article into an artificial characters-per-second target.
    speech = torch.cat(audio_parts, dim=1).clamp(-1.0, 1.0)
    duration = speech.shape[1] / model.sample_rate
    max_reasonable = max(40.0, speech_chars * 0.70)
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
        "inferenceMode": voice_policy.INFERENCE_MODE,
        "speed": voice_policy.VOICE_SPEED,
        "instructionPolicy": "none-reference-only",
        "languageGate": voice_policy.LANGUAGE_GATE,
        "segmentPolicy": voice_policy.SEGMENT_POLICY,
        "pacingPolicy": voice_policy.PACING_POLICY,
        "tempoPolicy": voice_policy.TEMPO_POLICY,
        "pauseMarkup": "punctuation-semantic",
        "inputTransport": "native-bistream-single-session",
        "streamInputChunkChars": STREAM_INPUT_CHARS,
        "streamInputChunkCounts": input_chunk_counts,
        "tempoFactors": [1.0],
    }


legacy.remote_reusable = _policy_remote_reusable
legacy.gen.setup_model = _setup_model_golden
legacy.gen.build_article_segments = _anchor_script_segments
legacy.gen.synthesize_story = _policy_synth
legacy.gen.can_reuse_legacy_lead = lambda *args, **kwargs: False

if __name__ == "__main__":
    raise SystemExit(legacy.main())
