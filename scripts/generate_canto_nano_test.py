#!/usr/bin/env python3
"""Generate public female-voice listening samples for canto-tts-nano-v1."""
from __future__ import annotations

import hashlib
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import soundfile as sf
from canto_tts import CantoTTS

OUT = Path("audio/canto-nano-test")
OUT.mkdir(parents=True, exist_ok=True)

# Same young female synthetic sample previously accepted during the Cantonese
# voice tests. canto-tts-nano's current ONNX backend can encode this reference
# at runtime and use the resulting prompt audio codes for voice cloning.
FEMALE_REFERENCE_URL = (
    "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/"
    "demo_page/raw/TTS_samples/9f24c7f95a2d040c43ce9fadfa56f6f3.wav"
)
FEMALE_REFERENCE_ASSET = "9f24c7f95a2d040c43ce9fadfa56f6f3.wav"
REFERENCE_MAX_SECONDS = 12.0
REFERENCE_MIN_SECONDS = 3.0

SAMPLES = [
    (
        "sample-short",
        "短句",
        "大家好，呢度係香港廣東話新聞語音測試。",
    ),
    (
        "sample-news",
        "一般新聞句",
        "香港天文台今日下午表示，本港部分地區錄得超過三十毫米雨量，提醒市民外出時留意天氣變化。",
    ),
    (
        "sample-numbers",
        "新聞長句／數字",
        "加拿大政府宣布，九月八日起對部分美國商品實施對等關稅措施，市場正關注下一輪貿易談判會否重啟，以及相關措施對消費者物價嘅影響。",
    ),
]


def prepare_female_reference() -> tuple[Path, float, str]:
    raw = Path("/tmp/canto-nano-female-reference-source.wav")
    ref = Path("/tmp/canto-nano-female-reference.wav")
    urllib.request.urlretrieve(FEMALE_REFERENCE_URL, raw)
    if not raw.is_file() or raw.stat().st_size < 50000:
        raise RuntimeError("female reference download is invalid")

    audio, sample_rate = sf.read(str(raw), dtype="float32", always_2d=True)
    if sample_rate <= 0 or audio.shape[0] <= 0:
        raise RuntimeError("female reference contains no usable audio")
    max_frames = int(round(sample_rate * REFERENCE_MAX_SECONDS))
    if audio.shape[0] > max_frames:
        audio = audio[:max_frames]
    duration = audio.shape[0] / sample_rate
    if duration < REFERENCE_MIN_SECONDS:
        raise RuntimeError(f"female reference is too short: {duration:.3f}s")
    sf.write(str(ref), audio, sample_rate, subtype="PCM_16")
    digest = hashlib.sha256(ref.read_bytes()).hexdigest()
    print(
        f"FEMALE_REFERENCE_READY asset={FEMALE_REFERENCE_ASSET} "
        f"duration={duration:.3f}s bytes={ref.stat().st_size} sha256={digest[:16]}",
        flush=True,
    )
    return ref, duration, digest


def main() -> int:
    female_ref, ref_duration, ref_sha = prepare_female_reference()
    tts = CantoTTS(backend="onnx")
    manifest = {
        "model": "typangaa/canto-tts-nano",
        "engine": "canto-tts-nano-v1",
        "language": "yue-HK",
        "quality": "duration_filter",
        "speaker": "female-cloned",
        "speakerMode": "runtime-ref-audio-voice-clone",
        "referenceAsset": FEMALE_REFERENCE_ASSET,
        "referenceDurationSeconds": round(ref_duration, 3),
        "referenceSha256": ref_sha,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "samples": [],
    }
    for sample_id, label, text in SAMPLES:
        out = OUT / f"{sample_id}.wav"
        print(f"Generating female {sample_id}: {text}", flush=True)
        tts.synthesize(
            text,
            str(out),
            ref_audio=str(female_ref),
            quality="duration_filter",
            max_attempts=3,
        )
        if not out.is_file() or out.stat().st_size < 50000:
            raise RuntimeError(f"invalid output: {out}")
        manifest["samples"].append({
            "id": sample_id,
            "label": label,
            "text": text,
            "speaker": "female-cloned",
            "audio": str(out).replace("\\", "/"),
            "bytes": out.stat().st_size,
            "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        })
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("CANTO_NANO_FEMALE_TEST_GENERATION_OK", len(SAMPLES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
