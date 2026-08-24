#!/usr/bin/env python3
"""Generate Cantonese news audio as reference-locked semantic units."""
import re
import sys
import time
import urllib.request
from pathlib import Path

import torch
import torchaudio

import cosyvoice_cache_identity as cache_identity
import cosyvoice_policy as voice_policy
import generate_cosyvoice_lead as voice_base
import generate_cosyvoice_shard as legacy
import tts_hktrad_v2 as hktrad

cache_identity.install(legacy.gen)

POLICY = voice_policy.POLICY
REFERENCE_POLICY = voice_policy.REFERENCE_POLICY
REFERENCE_ASSET = voice_policy.REFERENCE_ASSET
REFERENCE_URL = voice_policy.REFERENCE_URL
REFERENCE_START_SECONDS = voice_policy.REFERENCE_START_SECONDS
REFERENCE_DURATION_SECONDS = voice_policy.REFERENCE_DURATION_SECONDS
VOICE_RANDOM_SEED = 20260823
CANTONESE_INSTRUCT = "用粤语说这句话"

_ORIGINAL_NORMALIZE = voice_base.normalize_for_tts


def _localized_normalize(value):
    return hktrad.localize(_ORIGINAL_NORMALIZE(value))


voice_base.normalize_for_tts = _localized_normalize

PUNCT_KIND = {
    "，": "comma", ",": "comma", "、": "comma",
    "；": "semantic", ";": "semantic", "：": "semantic", ":": "semantic",
    "。": "sentence", "！": "sentence", "？": "sentence", "!": "sentence", "?": "sentence",
}
NUMBER_RE = re.compile(
    r"(?:[零一二三四五六七八九十百千萬億兆點]+(?:年|月|日|時|分|秒|人|宗|間|架|艘|部|公里|米|度|級)|"
    r"[零一二三四五六七八九十百千萬億兆點]+(?:百分比|美元|港元|英鎊|歐元|日圓)|"
    r"[0-9０-９]+(?:[\.．,，][0-9０-９]+)?(?:%|％|年|月|日|時|分|秒|人|宗|間|架|艘|部|公里|米|度|級|美元|港元|英鎊|歐元|日圓))"
)
REPORTING_VERBS = ("表示", "指出", "宣布", "稱", "認為", "警告", "強調", "證實")


def _setup_model():
    if not voice_base.CODE_ROOT.exists():
        raise RuntimeError(f"WenetSpeech-Yue code not found: {voice_base.CODE_ROOT}")
    voice_base.ensure_model()
    sys.path.insert(0, str(voice_base.CODE_ROOT))
    sys.path.insert(0, str(voice_base.CODE_ROOT / "third_party" / "Matcha-TTS"))
    voice_base.install_offline_wetext_stub()
    from cosyvoice.cli.cosyvoice import CosyVoice2
    from cosyvoice.utils.file_utils import load_wav

    ref = Path("/tmp/approved_young_female_reference.wav")
    urllib.request.urlretrieve(REFERENCE_URL, ref)
    if ref.stat().st_size < 50000:
        raise RuntimeError("approved young-female reference download is too small")

    print("Loading CosyVoice2-Yue semantic-unit runtime on CPU...", flush=True)
    t0 = time.time()
    model = CosyVoice2(str(voice_base.MODEL_DIR), load_jit=False, load_trt=False, load_vllm=False, fp16=False)
    prompt = load_wav(str(ref), 16000)
    start = int(round(REFERENCE_START_SECONDS * 16000))
    length = int(round(REFERENCE_DURATION_SECONDS * 16000))
    if start + length > prompt.shape[1]:
        start = max(0, prompt.shape[1] - length)
    prompt = prompt[:, start:start + length]
    if prompt.ndim != 2 or prompt.shape[1] < 16000 * 4:
        raise RuntimeError("approved young-female reference crop is too short")
    print(
        f"Reference={REFERENCE_ASSET} start={start/16000:.2f}s "
        f"duration={prompt.shape[1]/16000:.2f}s loaded_in={time.time()-t0:.1f}s",
        flush=True,
    )
    return model, prompt


def _collect_script(story):
    budget = int(getattr(legacy.gen, "ARTICLE_TEXT_LIMIT", 260) or 260)
    values, seen = [], set()

    def add(value):
        raw = legacy.gen.clean(value)
        if raw and raw not in seen:
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

    out, used = [], 0
    for raw in values:
        text = voice_base.normalize_for_tts(raw)
        if not text or used >= budget:
            continue
        text = text[: budget - used]
        used += len(text)
        if text and text[-1] not in "。！？!?":
            text += "。"
        out.append(text)
    script = "".join(out)
    if len(script) < 8:
        raise RuntimeError(f"story text too short for TTS: {story.get('title')!r}")
    residual = hktrad.residual_latin_tokens(script)
    if residual:
        raise RuntimeError(
            f"TTS residual Latin gate blocked {story.get('id') or story.get('title')}: " + ", ".join(residual)
        )
    return script


def _punctuation_pieces(text):
    text = str(text or "").replace(",", "，").replace(";", "；").replace(":", "：")
    out, start = [], 0
    for match in re.finditer(r"[。！？!?，、；：]", text):
        out.append(text[start:match.end()])
        start = match.end()
    if start < len(text):
        out.append(text[start:])
    return [piece.strip() for piece in out if piece.strip()]


def _safe_split(core):
    """Return conservative semantic chunks; never split just to hit a length."""
    core = core.strip()
    if not core:
        return []
    min_chars = voice_policy.MIN_SEMANTIC_SEGMENT_CHARS
    max_chars = voice_policy.MAX_SEMANTIC_SEGMENT_CHARS
    if len(core) <= max_chars:
        return [{"text": core, "pause": 0.0, "reason": "clause"}]

    # Long introductory modifier: pause only after the modifier is complete.
    intro = re.match(
        r"^((?:在|截至|隨著|由於|根據|按照|受)[^，。！？；：]{7,25}?(?:後|前|時|期間|之際|下|中|內|方面))(.{%d,})$" % min_chars,
        core,
    )
    if intro and len(intro.group(1)) >= min_chars:
        return [
            {"text": intro.group(1), "pause": voice_policy.COMMA_PAUSE_SECONDS, "reason": "modifier-boundary"},
            {"text": intro.group(2), "pause": 0.0, "reason": "continuation"},
        ]

    # Long subject before a reporting verb.
    for verb in REPORTING_VERBS:
        idx = core.find(verb)
        if min_chars <= idx <= 26 and len(core) - idx >= min_chars:
            return [
                {"text": core[:idx], "pause": voice_policy.COMMA_PAUSE_SECONDS, "reason": "subject-verb-boundary"},
                {"text": core[idx:], "pause": 0.0, "reason": "continuation"},
            ]

    # Briefly separate a reporting verb from a genuinely long object clause.
    for verb in REPORTING_VERBS:
        end = core.find(verb)
        if end >= 0:
            end += len(verb)
            if end >= min_chars and len(core) - end >= 16:
                return [
                    {"text": core[:end], "pause": voice_policy.COMMA_PAUSE_SECONDS, "reason": "before-long-object"},
                    {"text": core[end:], "pause": 0.0, "reason": "long-object"},
                ]

    return [{"text": core, "pause": 0.0, "reason": "unsplit-complete-clause"}]


def _number_refine(chunks):
    refined = []
    for chunk in chunks:
        text = chunk["text"]
        found = None
        for match in NUMBER_RE.finditer(text):
            left, right = text[:match.start()], text[match.end():]
            if len(left) >= 8 and len(right) >= 7:
                found = (left, match.group(0), right)
                break
        if not found:
            refined.append(chunk)
            continue
        left, number, right = found
        refined.append({"text": left, "pause": voice_policy.COMMA_PAUSE_SECONDS, "reason": "before-key-number"})
        refined.append({"text": number, "pause": voice_policy.COMMA_PAUSE_SECONDS, "reason": "key-number"})
        refined.append({"text": right, "pause": chunk["pause"], "reason": "after-key-number"})
    return [item for item in refined if item["text"].strip()]


def _delivery_units(script):
    units = []
    for piece in _punctuation_pieces(script):
        mark = piece[-1] if piece[-1] in PUNCT_KIND else ""
        core = piece[:-1].strip() if mark else piece.strip()
        chunks = _number_refine(_safe_split(core))
        if not chunks:
            continue
        if mark:
            chunks[-1]["text"] += mark
        if mark in ("，", ",", "、"):
            chunks[-1]["pause"] = max(chunks[-1]["pause"], voice_policy.COMMA_PAUSE_SECONDS)
            chunks[-1]["reason"] = "punctuation-comma"
        elif mark in ("；", ";", "：", ":"):
            chunks[-1]["pause"] = max(chunks[-1]["pause"], voice_policy.SEMICOLON_PAUSE_SECONDS)
            chunks[-1]["reason"] = "punctuation-semantic"
        elif mark in ("。",):
            chunks[-1]["pause"] = max(chunks[-1]["pause"], voice_policy.FULL_STOP_PAUSE_SECONDS)
            chunks[-1]["reason"] = "punctuation-sentence"
        elif mark in ("！", "？", "!", "?"):
            chunks[-1]["pause"] = max(chunks[-1]["pause"], voice_policy.QUESTION_PAUSE_SECONDS)
            chunks[-1]["reason"] = "punctuation-sentence"
        units.extend(chunks)
    return units


def _synth_unit(model, prompt, unit, index):
    text = unit["text"].strip()
    torch.manual_seed(VOICE_RANDOM_SEED)
    print(
        f"unit={index} chars={len(text)} reason={unit['reason']} pause={unit['pause']} "
        f"mode=instruct2 speed={voice_policy.VOICE_SPEED} text={text}",
        flush=True,
    )
    chunks = []
    with torch.inference_mode():
        for result in model.inference_instruct2(
            text,
            CANTONESE_INSTRUCT,
            prompt,
            stream=False,
            speed=voice_policy.VOICE_SPEED,
            text_frontend=True,
        ):
            speech = result["tts_speech"].detach().cpu()
            if speech.numel():
                chunks.append(speech)
    if not chunks:
        raise RuntimeError(f"CosyVoice2-Yue returned zero audio for semantic unit {index}")
    return torch.cat(chunks, dim=1)


def _policy_synth(model, prompt, story, path):
    script = _collect_script(story)
    units = _delivery_units(script)
    if not units:
        raise RuntimeError("semantic delivery produced zero units")

    parts = []
    for index, unit in enumerate(units):
        audio = _synth_unit(model, prompt, unit, index)
        parts.append(audio)
        pause = float(unit.get("pause") or 0)
        if pause > 0:
            parts.append(torch.zeros((1, int(round(model.sample_rate * pause))), dtype=audio.dtype))

    speech = torch.cat(parts, dim=1).clamp(-1.0, 1.0)
    duration = speech.shape[1] / model.sample_rate
    speech_chars = sum(len(unit["text"]) for unit in units)
    max_reasonable = max(45.0, speech_chars * 0.85)
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
        "segmentCount": len(units),
        "semanticUnitCount": len(units),
        "speechTextChars": speech_chars,
        "durationSeconds": round(duration, 3),
        "bytes": size,
        "prosodyPolicy": POLICY,
        "referencePolicy": REFERENCE_POLICY,
        "referenceAsset": REFERENCE_ASSET,
        "referenceStartSeconds": REFERENCE_START_SECONDS,
        "referenceDurationSeconds": REFERENCE_DURATION_SECONDS,
        "initialConditioningPolicy": voice_policy.INITIAL_CONDITIONING_POLICY,
        "randomSeed": VOICE_RANDOM_SEED,
        "inferenceMode": voice_policy.INFERENCE_MODE,
        "speed": voice_policy.VOICE_SPEED,
        "instructionPolicy": "instruct2-cantonese-control-not-spoken",
        "languageGate": voice_policy.LANGUAGE_GATE,
        "segmentPolicy": voice_policy.SEGMENT_POLICY,
        "pacingPolicy": voice_policy.PACING_POLICY,
        "pacingTarget": voice_policy.PACING_TARGET,
        "tempoPolicy": voice_policy.TEMPO_POLICY,
        "pauseMarkup": "silence-joined-semantic-units",
        "inputTransport": "per-semantic-unit-instruct2",
        "pauseProfile": {
            "comma": voice_policy.COMMA_PAUSE_SECONDS,
            "semantic": voice_policy.SEMICOLON_PAUSE_SECONDS,
            "sentence": voice_policy.FULL_STOP_PAUSE_SECONDS,
        },
        "semanticUnits": [{"text": u["text"], "pause": u["pause"], "reason": u["reason"]} for u in units],
        "tempoFactors": [1.0],
    }


def _policy_remote_reusable(previous, story, digest):
    old = legacy.gen.previous_entry_for_title(previous, legacy.gen.clean(story.get("title")))
    if not old or old.get("contentSha256") != digest or old.get("prosodyPolicy") != POLICY:
        return False
    audio = str(old.get("audio") or "")
    return bool(
        old.get("referencePolicy") == REFERENCE_POLICY
        and old.get("referenceAsset") == REFERENCE_ASSET
        and old.get("initialConditioningPolicy") == voice_policy.INITIAL_CONDITIONING_POLICY
        and old.get("segmentPolicy") == voice_policy.SEGMENT_POLICY
        and old.get("inferenceMode") == voice_policy.INFERENCE_MODE
        and old.get("pacingPolicy") == voice_policy.PACING_POLICY
        and old.get("tempoPolicy") == voice_policy.TEMPO_POLICY
        and int(old.get("segmentCount") or 0) >= 1
        and f"-{voice_policy.ASSET_NAMESPACE}-" in audio
        and audio.startswith(("https://", "http://"))
    )


legacy.remote_reusable = _policy_remote_reusable
legacy.gen.setup_model = _setup_model
legacy.gen.build_article_segments = lambda story: [{"role": "news", "text": _collect_script(story), "pause": 0.0}]
legacy.gen.synthesize_story = _policy_synth
legacy.gen.can_reuse_legacy_lead = lambda *args, **kwargs: False

if __name__ == "__main__":
    raise SystemExit(legacy.main())
