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

INSTRUCT = "用粤语说这句话"
F01_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav"
REPO_ROOT = Path(os.environ.get("WSYUE_ROOT", "/tmp/WenetSpeech-Yue"))
CODE_ROOT = REPO_ROOT / "CosyVoice2-Yue"
MODEL_DIR = Path(os.environ.get("COSY_MODEL_DIR", "/tmp/Cosyvoice2-Yue"))
LATEST = Path(os.environ.get("COSY_LATEST_JSON", "data/latest.json"))
OUTPUT = Path(os.environ.get("COSY_OUTPUT_WAV", "assets/audio/cosyvoice/latest-lead.wav"))
MANIFEST = Path(os.environ.get("COSY_MANIFEST_JSON", "data/tts-manifest.json"))
MAX_TEXT_CHARS = int(os.environ.get("COSY_MAX_TEXT_CHARS", "520"))


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


def with_stop(value):
    text = clean_text(value)
    if text and text[-1] not in "。！？!?…":
        text += "。"
    return text


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

    parts = [with_stop(article.get("title")), with_stop(article.get("dek"))]
    paragraphs = [clean_text(p) for p in re.split(r"\n\s*\n", str(article.get("body") or "")) if clean_text(p)]
    parts.extend(with_stop(p) for p in paragraphs[:2])
    text = "\n\n".join(part for part in parts if part)[:MAX_TEXT_CHARS]
    if len(text) < 24:
        raise RuntimeError("lead article text is too short for TTS")
    return data, article, lead_id, text, source_sha256


def main():
    print("=== COSYVOICE2-YUE PRODUCTION LEAD GENERATOR ===", flush=True)
    if not CODE_ROOT.exists():
        raise RuntimeError(f"WenetSpeech-Yue code not found: {CODE_ROOT}")

    data, article, lead_id, text, source_sha256 = load_lead()
    print(f"lead_id={lead_id}", flush=True)
    print(f"title={article.get('title')}", flush=True)
    print(f"tts_chars={len(text)}", flush=True)
    print(f"source_sha256={source_sha256}", flush=True)

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
    chunks = []
    print("Synthesizing production Daily lead with F01 female reference...", flush=True)
    t1 = time.time()
    with torch.inference_mode():
        for idx, result in enumerate(cosyvoice.inference_instruct2(text, INSTRUCT, prompt_speech_16k, stream=False)):
            speech = result["tts_speech"].detach().cpu()
            print(f"chunk={idx} shape={tuple(speech.shape)}", flush=True)
            chunks.append(speech)

    if not chunks:
        raise RuntimeError("CosyVoice2-Yue returned zero production audio chunks")

    speech = torch.cat(chunks, dim=1)
    duration = speech.shape[1] / cosyvoice.sample_rate
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(OUTPUT), speech, cosyvoice.sample_rate, backend="soundfile")
    size = OUTPUT.stat().st_size
    if duration < 2.0 or size < 50000:
        raise RuntimeError(f"invalid production audio: duration={duration:.3f}s bytes={size}")

    manifest = {
        "version": 1,
        "engine": "ASLP-lab/Cosyvoice2-Yue",
        "voice": "F01 female reference",
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
                "durationSeconds": round(duration, 3),
                "bytes": size,
            }
        },
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Generated duration={duration:.3f}s bytes={size} inference_seconds={time.time() - t1:.1f}", flush=True)
    print(f"COSYVOICE_PRODUCTION_PASS={OUTPUT}", flush=True)
    print(f"COSYVOICE_MANIFEST={MANIFEST}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
