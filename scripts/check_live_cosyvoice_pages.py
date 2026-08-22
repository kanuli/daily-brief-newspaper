#!/usr/bin/env python3
import json
import struct
import time
import urllib.request
from pathlib import Path

BASE = "https://kanuli.github.io/daily-brief-newspaper/"
LOCAL_MANIFEST = Path("data/tts-manifest.json")
ATTEMPTS = 30
SLEEP_SECONDS = 5


def get(url, method="GET"):
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "daily-brief-cosyvoice-live-smoke/2.0", "Cache-Control": "no-cache"},
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return response.status, response.headers, response.read() if method != "HEAD" else b""


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
    fmt["dataBytes"] = data_size
    fmt["duration"] = data_size / float(fmt["byteRate"])
    return fmt


def validate_once(expected):
    stamp = str(int(time.time() * 1000))
    status, _, body = get(f"{BASE}data/tts-manifest.json?smoke={stamp}")
    if status != 200:
        raise RuntimeError(f"manifest HTTP {status}")
    remote = json.loads(body.decode("utf-8"))

    for key in ("engine", "voice", "language", "pronunciationPolicy", "coveragePolicy", "leadId", "sourceSetSha256"):
        if expected.get(key) is not None and remote.get(key) != expected.get(key):
            raise RuntimeError(f"live manifest {key} mismatch: {remote.get(key)!r} != {expected.get(key)!r}")

    expected_articles = expected.get("articles") or {}
    remote_articles = remote.get("articles") or {}
    if len(remote_articles) != len(expected_articles):
        raise RuntimeError(f"live manifest article count mismatch: {len(remote_articles)} != {len(expected_articles)}")
    if remote.get("articleCount") != len(remote_articles):
        raise RuntimeError("live manifest articleCount is inconsistent")

    # Every current story must expose an actual F01 WAV URL. HEAD avoids downloading
    # the entire corpus while still proving Pages published every file.
    checked = 0
    for key, expected_entry in expected_articles.items():
        entry = remote_articles.get(key)
        if not entry:
            raise RuntimeError(f"live manifest missing article {key}")
        for field in ("title", "audio", "wavEncoding", "contentSha256", "bytes"):
            if entry.get(field) != expected_entry.get(field):
                raise RuntimeError(f"live article {key} {field} mismatch")
        if entry.get("wavEncoding") != "PCM16":
            raise RuntimeError(f"live article {key} is not PCM16")
        audio_path = entry.get("audio")
        status, headers, _ = get(f"{BASE}{audio_path}?smoke={stamp}", method="HEAD")
        if status != 200:
            raise RuntimeError(f"audio HEAD {status}: {audio_path}")
        content_length = headers.get("Content-Length")
        if content_length and int(content_length) != int(entry.get("bytes") or 0):
            raise RuntimeError(f"audio bytes mismatch for {audio_path}: {content_length} != {entry.get('bytes')}")
        checked += 1

    lead_title = expected.get("leadTitle")
    lead_entry = next((entry for entry in remote_articles.values() if entry.get("title") == lead_title), None)
    if not lead_entry:
        raise RuntimeError("live manifest has no lead-title F01 entry")
    status, headers, wav_bytes = get(f"{BASE}{lead_entry['audio']}?smoke={stamp}")
    if status != 200:
        raise RuntimeError(f"lead audio HTTP {status}")
    info = wav_info(wav_bytes)
    if info["audioFormat"] != 1 or info["bits"] != 16 or info["duration"] <= 2:
        raise RuntimeError(
            f"lead F01 WAV invalid format={info['audioFormat']} bits={info['bits']} duration={info['duration']:.3f}"
        )

    print(
        "COSYVOICE_LIVE_ALL_NEWS_PASS "
        f"articles={checked} lead_bytes={len(wav_bytes)} lead_duration={info['duration']:.3f}s "
        f"format={info['audioFormat']} bits={info['bits']} content_type={headers.get('Content-Type')}"
    )


def main():
    expected = json.loads(LOCAL_MANIFEST.read_text(encoding="utf-8"))
    if expected.get("engine") != "ASLP-lab/Cosyvoice2-Yue":
        raise RuntimeError("local manifest is not CosyVoice2-Yue")
    if expected.get("voice") != "F01 female reference":
        raise RuntimeError("local manifest is not F01 female reference")
    if expected.get("coveragePolicy") != "all-current-news-f01-only":
        raise RuntimeError("local manifest is not all-news F01-only")

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
    raise RuntimeError(f"live GitHub Pages all-news F01 validation failed: {last_error}")


if __name__ == "__main__":
    raise SystemExit(main())
