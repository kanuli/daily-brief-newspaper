#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
import time
import types
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import torch
import torchaudio
from huggingface_hub import snapshot_download

# Keep the dialect instruction short. A long assistant-style prompt can leak
# into generated speech with CosyVoice2 instruct inference.
INSTRUCT = "用地道香港粤语说这句话"
F01_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav"
REPO_ROOT = Path(os.environ.get("WSYUE_ROOT", "/tmp/WenetSpeech-Yue"))
CODE_ROOT = REPO_ROOT / "CosyVoice2-Yue"
MODEL_DIR = Path(os.environ.get("COSY_MODEL_DIR", "/tmp/Cosyvoice2-Yue"))
LATEST = Path(os.environ.get("COSY_LATEST_JSON", "data/latest.json"))
OUTPUT = Path(os.environ.get("COSY_OUTPUT_WAV", "assets/audio/cosyvoice/latest-lead.wav"))
MANIFEST = Path(os.environ.get("COSY_MANIFEST_JSON", "data/tts-manifest.json"))
MAX_TEXT_CHARS = int(os.environ.get("COSY_MAX_TEXT_CHARS", "520"))
MAX_SEGMENT_CHARS = int(os.environ.get("COSY_MAX_SEGMENT_CHARS", "64"))

TITLE_PAUSE_SECONDS = 0.80
DEK_PAUSE_SECONDS = 0.65
BODY_PAUSE_SECONDS = 0.26
INTERNAL_SPLIT_PAUSE_SECONDS = 0.18
_DIGITS = "零一二三四五六七八九"


class LocalNormalizer:
    def __init__(self, *args, **kwargs):
        pass

    def normalize(self, text):
        return text


def install_offline_wetext_stub():
    module = types.ModuleType("wetext")
    module.Normalizer = LocalNormalizer
    sys.modules["wetext"] = module
    print("Using local pass-through text normalizer; no ModelScope FST download", flush=True)


def ensure_model():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print("Ensuring CPU-required ASLP-lab/Cosyvoice2-Yue files...", flush=True)
    snapshot_download(
        repo_id="ASLP-lab/Cosyvoice2-Yue",
        local_dir=str(MODEL_DIR),
        allow_patterns=[
            "cosyvoice2.yaml", "configuration.json", "campplus.onnx",
            "speech_tokenizer_v2.onnx", "spk2info.pt", "llm.pt",
            "flow.pt", "hift.pt", "CosyVoice-BlankEN/*",
        ],
    )


def clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _small_integer_to_chinese(number):
    number = int(number)
    if number < 10:
        return _DIGITS[number]
    if number < 100:
        tens, ones = divmod(number, 10)
        head = "十" if tens == 1 else f"{_DIGITS[tens]}十"
        return head + (_DIGITS[ones] if ones else "")
    if number < 1000:
        hundreds, remainder = divmod(number, 100)
        out = f"{_DIGITS[hundreds]}百"
        if remainder:
            if remainder < 10:
                out += "零"
            out += _small_integer_to_chinese(remainder)
        return out
    if number < 10000:
        thousands, remainder = divmod(number, 1000)
        out = f"{_DIGITS[thousands]}千"
        if remainder:
            if remainder < 100:
                out += "零"
            out += _small_integer_to_chinese(remainder)
        return out
    return "".join(_DIGITS[int(char)] for char in str(number))


def _number_string_for_speech(raw):
    raw = str(raw)
    if len(raw) == 4 and raw.isdigit() and 1900 <= int(raw) <= 2099:
        return "".join(_DIGITS[int(char)] for char in raw)
    if raw.isdigit() and int(raw) < 10000:
        return _small_integer_to_chinese(int(raw))
    if raw.isdigit():
        return "".join(_DIGITS[int(char)] for char in raw)
    return raw


def _number_for_speech(match):
    raw = match.group(0).replace(",", "")
    if "." in raw:
        whole, fraction = raw.split(".", 1)
        return f"{_number_string_for_speech(whole)}點{''.join(_DIGITS[int(c)] for c in fraction)}"
    return _number_string_for_speech(raw)


def normalize_numbers_for_cantonese(text):
    text = re.sub(r"(?<![A-Za-z])\d[\d,]*(?:\.\d+)?", _number_for_speech, text)
    text = text.replace("%", "百分比")
    text = text.replace("£", "英鎊").replace("€", "歐元").replace("$", "美元")
    return text


def normalize_for_tts(value):
    text = clean_text(value)
    text = re.sub(r"[「『“\"]?double[\-‐‑–— ]?tap[」』”\"]?", "二次打擊", text, flags=re.IGNORECASE)
    text = re.sub(r"\bReuters\b", "路透社", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAssociated Press\b", "美聯社", text, flags=re.IGNORECASE)
    text = re.sub(r"\bAP\b", "美聯社", text)
    text = normalize_numbers_for_cantonese(text)
    text = text.replace("–", "，").replace("—", "，")
    return clean_text(text)


def with_stop(value):
    text = normalize_for_tts(value)
    if text and text[-1] not in "。！？!?…":
        text += "。"
    return text


def split_long_piece(piece, max_chars):
    piece = clean_text(piece)
    out = []
    while len(piece) > max_chars:
        window = piece[: max_chars + 1]
        cut = max_chars
        for marker in ("，", ",", "、", "：", ":", " "):
            idx = window.rfind(marker)
            if idx >= max(12, max_chars // 2):
                cut = idx + 1
                break
        head = clean_text(piece[:cut])
        if head:
            out.append(head)
        piece = clean_text(piece[cut:])
    if piece:
        out.append(piece)
    return out


def split_for_tts(value, max_chars=MAX_SEGMENT_CHARS):
    text = normalize_for_tts(value)
    if not text:
        return []
    strong = [clean_text(p) for p in re.split(r"(?<=[。！？!?；;])", text) if clean_text(p)]
    atoms = []
    for piece in strong:
        atoms.extend(split_long_piece(piece, max_chars))
    segments, buffer = [], ""
    for atom in atoms:
        candidate = clean_text(f"{buffer}{atom}") if buffer else atom
        if buffer and len(candidate) > max_chars:
            segments.append(with_stop(buffer))
            buffer = atom
        else:
            buffer = candidate
    if buffer:
        segments.append(with_stop(buffer))
    return [segment for segment in segments if segment]


def add_role_segments(target, role, text, final_pause):
    pieces = split_for_tts(text)
    for idx, piece in enumerate(pieces):
        pause = final_pause if idx == len(pieces) - 1 else INTERNAL_SPLIT_PAUSE_SECONDS
        target.append({"role": role, "text": piece, "pause": pause})


def build_tts_segments(article):
    segments = []
    budget = MAX_TEXT_CHARS
    fields = [
        ("title", article.get("title"), TITLE_PAUSE_SECONDS),
        ("dek", article.get("dek"), DEK_PAUSE_SECONDS),
    ]
    paragraphs = [clean_text(p) for p in re.split(r"\n\s*\n", str(article.get("body") or "")) if clean_text(p)]
    fields.extend(("body", paragraph, BODY_PAUSE_SECONDS) for paragraph in paragraphs[:2])
    for role, raw_text, final_pause in fields:
        text = normalize_for_tts(raw_text)
        if not text or budget <= 0:
            continue
        if len(text) > budget:
            text = text[:budget]
        budget -= len(text)
        add_role_segments(segments, role, text, final_pause)
    if not segments or sum(len(item["text"]) for item in segments) < 24:
        raise RuntimeError("lead article text is too short for TTS")
    return segments


def load_lead():
    source_bytes = LATEST.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    data = json.loads(source_bytes.decode("utf-8"))
    lead_id = data.get("leadId")
    articles = data.get("articles") or []
    article = next((item for item in articles if item.get("id") == lead_id), None)
    if article is None and articles:
        article = articles[0]
        lead_id = article.get("id")
    if not article or not lead_id:
        raise RuntimeError("data/latest.json has no usable lead article")
    return data, article, lead_id, build_tts_segments(article), source_sha256


def synthesize_segment(cosyvoice, prompt_speech_16k, item, index):
    text = item["text"]
    print(f"segment={index} role={item['role']} chars={len(text)} text={text}", flush=True)
    chunks = []
    with torch.inference_mode():
        for chunk_idx, result in enumerate(cosyvoice.inference_instruct2(text, INSTRUCT, prompt_speech_16k, stream=False)):
            speech = result["tts_speech"].detach().cpu()
            if speech.numel() == 0:
                continue
            print(f"segment={index} chunk={chunk_idx} shape={tuple(speech.shape)}", flush=True)
            chunks.append(speech)
    if not chunks:
        raise RuntimeError(f"CosyVoice2-Yue returned zero audio for segment {index}: {text}")
    return torch.cat(chunks, dim=1)


def main():
    print("=== COSYVOICE2-YUE PRODUCTION LEAD GENERATOR ===", flush=True)
    if not CODE_ROOT.exists():
        raise RuntimeError(f"WenetSpeech-Yue code not found: {CODE_ROOT}")
    data, article, lead_id, segments, source_sha256 = load_lead()
    speech_chars = sum(len(item["text"]) for item in segments)
    print(f"lead_id={lead_id}", flush=True)
    print(f"title={article.get('title')}", flush=True)
    print(f"tts_segments={len(segments)} tts_chars={speech_chars}", flush=True)
    print(f"source_sha256={source_sha256}", flush=True)
    print("pronunciation_policy=yue-HK-cantonese-only; instruct=short-no-leak", flush=True)
    ensure_model()
    sys.path.insert(0, str(CODE_ROOT))
    sys.path.insert(0, str(CODE_ROOT / "third_party" / "Matcha-TTS"))
    install_offline_wetext_stub()
    from cosyvoice.cli.cosyvoice import CosyVoice2
    from cosyvoice.utils.file_utils import load_wav

    ref = Path("/tmp/F01_female.wav")
    urllib.request.urlretrieve(F01_URL, ref)
    if ref.stat().st_size < 10000:
        raise RuntimeError("F01 female reference download is too small")
    print("Loading CosyVoice2-Yue on CPU...", flush=True)
    t0 = time.time()
    cosyvoice = CosyVoice2(str(MODEL_DIR), load_jit=False, load_trt=False, load_vllm=False, fp16=False)
    print(f"Model loaded in {time.time() - t0:.1f}s sample_rate={cosyvoice.sample_rate}", flush=True)
    prompt_speech_16k = load_wav(str(ref), 16000)
    audio_parts = []
    t1 = time.time()
    for idx, item in enumerate(segments):
        segment_audio = synthesize_segment(cosyvoice, prompt_speech_16k, item, idx)
        audio_parts.append(segment_audio)
        pause_samples = int(round(cosyvoice.sample_rate * item["pause"]))
        if pause_samples > 0:
            audio_parts.append(torch.zeros((1, pause_samples), dtype=segment_audio.dtype))
    if not audio_parts:
        raise RuntimeError("CosyVoice2-Yue returned zero production audio")
    speech = torch.cat(audio_parts, dim=1).clamp(-1.0, 1.0)
    duration = speech.shape[1] / cosyvoice.sample_rate
    # Guard against accidental spoken-instruction leakage. The bad long-prompt
    # build was ~200 s for this article; normal news speech should stay well
    # below this conservative text-length envelope.
    max_reasonable_duration = max(60.0, speech_chars * 0.45)
    if duration > max_reasonable_duration:
        raise RuntimeError(
            f"production audio suspiciously long; possible prompt leakage: duration={duration:.3f}s "
            f"limit={max_reasonable_duration:.3f}s chars={speech_chars}"
        )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(OUTPUT), speech, cosyvoice.sample_rate, encoding="PCM_S", bits_per_sample=16, backend="soundfile")
    size = OUTPUT.stat().st_size
    if duration < 2.0 or size < 50000:
        raise RuntimeError(f"invalid production audio: duration={duration:.3f}s bytes={size}")
    manifest = {
        "version": 1,
        "engine": "ASLP-lab/Cosyvoice2-Yue",
        "voice": "F01 female reference",
        "language": "yue-HK",
        "pronunciationPolicy": "cantonese-only",
        "instructionPolicy": "short-no-leak",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "source": "data/latest.json",
        "sourceSha256": source_sha256,
        "date": data.get("date"),
        "leadId": lead_id,
        "articles": {
            lead_id: {
                "articleId": lead_id,
                "title": clean_text(article.get("title")),
                "audio": OUTPUT.as_posix(),
                "wavEncoding": "PCM16",
                "segmentCount": len(segments),
                "speechTextChars": speech_chars,
                "durationSeconds": round(duration, 3),
                "bytes": size,
            }
        },
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated duration={duration:.3f}s bytes={size} encoding=PCM16 segments={len(segments)} inference_seconds={time.time()-t1:.1f}", flush=True)
    print(f"COSYVOICE_PRODUCTION_PASS={OUTPUT}", flush=True)
    print(f"COSYVOICE_MANIFEST={MANIFEST}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
