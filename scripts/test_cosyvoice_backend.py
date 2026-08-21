#!/usr/bin/env python3
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from gradio_client import Client, handle_file

F01_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav"
INSTRUCT = "You are a helpful assistant. 请用广东话表达。<|endofprompt|>"
TEST_TEXT = "今日香港天氣很好。這是一段廣東話語音測試。"
BACKENDS = [
    ("Originalmmd/CosyVoice3-VoiceStudio", "instruct"),
    ("recentechstudio/CosyVoice3", "zero-shot"),
]


def endpoint_candidates(api, mode):
    endpoints = []
    for group in ("named_endpoints", "unnamed_endpoints"):
        for key, info in (api.get(group) or {}).items():
            params = info.get("parameters") or []
            labels = [str(p.get("label") or "").strip().lower() for p in params]
            score = 0
            if any("text to synthesize" in x or x == "text" or "text to speak" in x for x in labels):
                score += 30
            if any("reference audio" in x or "voice sample" in x for x in labels):
                score += 30
            if mode == "instruct" and any("instruction" in x for x in labels):
                score += 100
            if mode == "zero-shot" and len(labels) <= 3:
                score += 20
            endpoints.append((score, key, info, group == "named_endpoints"))
    return sorted(endpoints, reverse=True, key=lambda x: x[0])


def build_payload(info, mode, ref_path):
    values = []
    for p in info.get("parameters") or []:
        label = str(p.get("label") or "").strip().lower()
        if "text to synthesize" in label or label == "text" or "text to speak" in label:
            values.append(TEST_TEXT)
        elif "instruction" in label:
            values.append(INSTRUCT)
        elif "reference audio" in label or "voice sample" in label:
            values.append(handle_file(str(ref_path)))
        elif "prompt text" in label:
            values.append("")
        elif "speed" in label:
            values.append(1.0)
        elif "seed" in label:
            values.append(42)
        elif "stream" in label:
            values.append(False)
        else:
            values.append(p.get("example_input", p.get("default")))
    return values


def extract_audio_path(value):
    if isinstance(value, str):
        p = Path(value)
        return p if p.exists() else None
    if isinstance(value, dict):
        for key in ("path", "url"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                p = Path(candidate)
                if p.exists():
                    return p
        for v in value.values():
            found = extract_audio_path(v)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for v in value:
            found = extract_audio_path(v)
            if found:
                return found
    return None


def prepare_reference(tmpdir: Path):
    raw = tmpdir / "f01_raw.wav"
    out = tmpdir / "f01_6s_16k.wav"
    urllib.request.urlretrieve(F01_URL, raw)
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(raw), "-t", "6", "-ac", "1", "-ar", "16000", str(out)
    ], check=True)
    if not out.exists() or out.stat().st_size < 10000:
        raise RuntimeError("prepared F01 reference is missing or too small")
    return out


def test_backend(space_id, mode, ref_path, output_dir):
    print(f"\n=== TEST {space_id} ({mode}) ===", flush=True)
    client = Client(space_id, verbose=True)
    api = client.view_api(return_format="dict")
    print(json.dumps(api, ensure_ascii=False, indent=2)[:20000], flush=True)

    candidates = endpoint_candidates(api, mode)
    if not candidates:
        raise RuntimeError("no API endpoints exposed")

    errors = []
    for score, key, info, named in candidates[:5]:
        if score < 30:
            continue
        api_name = key if named else (int(key) if str(key).isdigit() else key)
        payload = build_payload(info, mode, ref_path)
        print(f"Trying endpoint={api_name!r} score={score} payload_count={len(payload)}", flush=True)
        try:
            result = client.predict(*payload, api_name=api_name if named else None, fn_index=None if named else api_name)
            print(f"Result type={type(result).__name__}: {result!r}", flush=True)
            audio_path = extract_audio_path(result)
            if not audio_path:
                errors.append(f"{api_name}: no audio path in result")
                continue
            size = audio_path.stat().st_size
            print(f"Audio path={audio_path} size={size}", flush=True)
            if size < 5000:
                errors.append(f"{api_name}: audio too small ({size} bytes)")
                continue
            target = output_dir / f"cosyvoice-smoke-{space_id.split('/')[-1]}.wav"
            shutil.copyfile(audio_path, target)
            print(f"PASS {space_id}: {target} ({target.stat().st_size} bytes)", flush=True)
            return target
        except Exception as exc:
            errors.append(f"{api_name}: {type(exc).__name__}: {exc}")
            print(errors[-1], flush=True)

    raise RuntimeError("; ".join(errors) or "all candidate endpoints failed")


def main():
    output_dir = Path("artifacts/cosyvoice-smoke")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        ref_path = prepare_reference(Path(td))
        all_errors = []
        for space_id, mode in BACKENDS:
            try:
                path = test_backend(space_id, mode, ref_path, output_dir)
                print(f"\nCOSYVOICE_SMOKE_PASS={path}", flush=True)
                return 0
            except Exception as exc:
                msg = f"{space_id}: {type(exc).__name__}: {exc}"
                all_errors.append(msg)
                print(f"FAIL {msg}", flush=True)
        print("\nALL COSYVOICE BACKENDS FAILED", flush=True)
        for err in all_errors:
            print(f" - {err}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
