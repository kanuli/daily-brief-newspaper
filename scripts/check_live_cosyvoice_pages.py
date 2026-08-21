#!/usr/bin/env python3
import json
import struct
import time
import urllib.request
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


def wav_info(data):
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise RuntimeError("live audio is not a RIFF/WAVE file")

    pos = 12
    fmt = None
    data_size = None
    while pos + 8 <= len(data):
        chunk_id = data[pos:pos + 4]
        chunk_size = struct.unpack_from("<I", data, pos + 4)[0]
        start = pos + 8
        end = start + chunk_size
        if end > len(data):
            raise RuntimeError(f"truncated WAV chunk {chunk_id!r}")
        if chunk_id == b"fmt " and chunk_size >= 16:
            audio_format, channels, rate, byte_rate, block_align, bits = struct.unpack_from("<HHIIHH", data, start)
            fmt = {
                "audioFormat": audio_format,
                "channels": channels,
                "rate": rate,
                "byteRate": byte_rate,
                "blockAlign": block_align,
                "bits": bits,
            }
        elif chunk_id == b"data":
            data_size = chunk_size
        pos = end + (chunk_size & 1)

    if not fmt or data_size is None:
        raise RuntimeError("WAV is missing fmt or data chunk")
    if fmt["byteRate"] <= 0:
        raise RuntimeError("WAV has invalid byte rate")
    fmt["dataBytes"] = data_size
    fmt["duration"] = data_size / float(fmt["byteRate"])
    return fmt


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
    expected_entry = expected.get("articles", {}).get(lead_id, {})
    entry = remote.get("articles", {}).get(lead_id)
    if not entry:
        raise RuntimeError(f"live manifest missing lead article {lead_id}")

    expected_encoding = expected_entry.get("wavEncoding")
    if expected_encoding and entry.get("wavEncoding") != expected_encoding:
        raise RuntimeError(
            f"live manifest wavEncoding mismatch: {entry.get('wavEncoding')!r} != {expected_encoding!r}"
        )

    audio_path = entry.get("audio")
    if not audio_path:
        raise RuntimeError("live manifest audio path missing")

    status, headers, wav_bytes = get(f"{BASE}{audio_path}?smoke={stamp}")
    if status != 200:
        raise RuntimeError(f"audio HTTP {status}")
    if len(wav_bytes) < 50000:
        raise RuntimeError(f"live WAV too small: {len(wav_bytes)} bytes")

    info = wav_info(wav_bytes)
    if info["duration"] <= 2:
        raise RuntimeError(f"live WAV duration too short: {info['duration']:.3f}s")
    if info["audioFormat"] not in (1, 3):
        raise RuntimeError(f"unsupported WAV format code: {info['audioFormat']}")
    if expected_encoding == "PCM16":
        if info["audioFormat"] != 1 or info["bits"] != 16:
            raise RuntimeError(
                f"expected browser-safe PCM16, got format={info['audioFormat']} bits={info['bits']}"
            )

    expected_bytes = int(expected_entry.get("bytes") or 0)
    if expected_bytes and len(wav_bytes) != expected_bytes:
        raise RuntimeError(f"live WAV bytes mismatch: {len(wav_bytes)} != {expected_bytes}")

    print(
        "COSYVOICE_LIVE_PAGES_PASS "
        f"leadId={lead_id} bytes={len(wav_bytes)} duration={info['duration']:.3f}s "
        f"format={info['audioFormat']} bits={info['bits']} rate={info['rate']} "
        f"channels={info['channels']} content_type={headers.get('Content-Type')}"
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
