#!/usr/bin/env python3
import io
import json
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path

BASE = "https://kanuli.github.io/daily-brief-newspaper/"
LOCAL_MANIFEST = Path("data/tts-manifest.json")
ATTEMPTS = 24
SLEEP_SECONDS = 5


def get(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "daily-brief-cosyvoice-live-smoke/1.0", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, response.headers, response.read()


def validate_once(expected):
    stamp = str(int(time.time() * 1000))
    status, _, body = get(f"{BASE}data/tts-manifest.json?smoke={stamp}")
    if status != 200:
        raise RuntimeError(f"manifest HTTP {status}")
    remote = json.loads(body.decode("utf-8"))

    for key in ("engine", "voice", "leadId", "sourceSha256"):
        if remote.get(key) != expected.get(key):
            raise RuntimeError(f"live manifest {key} mismatch: {remote.get(key)!r} != {expected.get(key)!r}")

    lead_id = expected["leadId"]
    entry = remote.get("articles", {}).get(lead_id)
    if not entry:
        raise RuntimeError(f"live manifest missing lead article {lead_id}")
    audio_path = entry.get("audio")
    if not audio_path:
        raise RuntimeError("live manifest audio path missing")

    status, headers, wav_bytes = get(f"{BASE}{audio_path}?smoke={stamp}")
    if status != 200:
        raise RuntimeError(f"audio HTTP {status}")
    if len(wav_bytes) < 50000:
        raise RuntimeError(f"live WAV too small: {len(wav_bytes)} bytes")
    if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
        raise RuntimeError("live audio is not a RIFF/WAVE file")

    with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
        frames = wav.getnframes()
        rate = wav.getframerate()
        channels = wav.getnchannels()
        duration = frames / float(rate)
    if duration <= 2:
        raise RuntimeError(f"live WAV duration too short: {duration:.3f}s")

    expected_entry = expected.get("articles", {}).get(lead_id, {})
    expected_bytes = int(expected_entry.get("bytes") or 0)
    if expected_bytes and len(wav_bytes) != expected_bytes:
        raise RuntimeError(f"live WAV bytes mismatch: {len(wav_bytes)} != {expected_bytes}")

    print(
        "COSYVOICE_LIVE_PAGES_PASS "
        f"leadId={lead_id} bytes={len(wav_bytes)} duration={duration:.3f}s "
        f"rate={rate} channels={channels} content_type={headers.get('Content-Type')}"
    )


def main():
    expected = json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))
    if expected.get("engine") != "ASLP-lab/Cosyvoice2-Yue":
        raise RuntimeError("local manifest is not CosyVoice2-Yue")
    if expected.get("voice") != "F01 female reference":
        raise RuntimeError("local manifest is not F01 female reference")

    last_error = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            validate_once(expected)
            return 0
        except Exception as error:
            last_error = error
            print(f"live smoke attempt {attempt}/{ATTEMPTS} not ready: {error}", flush=True)
            if attempt < ATTEMPTS:
                time.sleep(SLEEP_SECONDS)
    raise RuntimeError(f"live GitHub Pages CosyVoice validation failed: {last_error}")


if __name__ == "__main__":
    raise SystemExit(main())
