#!/usr/bin/env python3
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

import requests
from gradio_client import Client, handle_file

F01_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav"
INSTRUCT = "You are a helpful assistant. 请用广东话表达。<|endofprompt|>"
TEST_TEXT = "今日香港天氣很好。這是一段廣東話語音測試。"

# This exact API-dedicated address was returned by the live ModelScope Studio
# proxy itself (HTTP 403 response), so test it directly instead of guessing.
MODELSCOPE_BASES = [
    "https://studio-funaudiollm-fun-cosyvoice3-0-5b.api-inference.modelscope.net/",
]

# These HF runtimes are diagnostic only. They already failed real E2E runs and
# must never be promoted to production unless a later run returns a real WAV.
HF_DIAGNOSTICS = [
    ("Originalmmd/CosyVoice3-VoiceStudio", "instruct"),
    ("recentechstudio/CosyVoice3", "zero-shot"),
]


def label_text(p):
    return str(p.get("label") or p.get("parameter_name") or "").strip().lower()


def endpoint_candidates(api, mode):
    endpoints = []
    for group in ("named_endpoints", "unnamed_endpoints"):
        for key, info in (api.get(group) or {}).items():
            params = info.get("parameters") or []
            labels = [label_text(p) for p in params]
            score = 0
            if any("text to synthesize" in x or "text to synthesise" in x or x == "text" or "text to speak" in x or "输入合成文本" in x for x in labels):
                score += 30
            if any("reference audio" in x or "voice sample" in x or "prompt audio" in x or "prompt_wav" in x or "prompt音频" in x for x in labels):
                score += 30
            if mode == "instruct" and any("instruction" in x or "instruct" in x or "自然语言" in x for x in labels):
                score += 100
            if mode == "zero-shot" and any("prompt text" in x or "prompt文本" in x for x in labels):
                score += 40
            endpoints.append((score, key, info, group == "named_endpoints"))
    return sorted(endpoints, reverse=True, key=lambda x: x[0])


def param_value(p, mode, ref_path):
    label = label_text(p)
    name = str(p.get("parameter_name") or "").lower()
    token = f"{label} {name}"
    if "text to synthesize" in token or "text to synthesise" in token or "text to speak" in token or token.strip() == "text" or "输入合成文本" in token or name == "tts_text":
        return TEST_TEXT
    if "instruction" in token or "instruct" in token:
        return INSTRUCT
    if "reference audio" in token or "voice sample" in token or "prompt audio" in token or "prompt_wav" in token or "prompt音频" in token:
        return handle_file(str(ref_path))
    if "prompt text" in token or "prompt文本" in token:
        return ""
    if "mode" in token and mode == "instruct":
        return "instruct"
    if "mode" in token and mode == "zero-shot":
        return "zero_shot"
    if "speed" in token:
        return 1.0
    if "seed" in token:
        return 42
    if "stream" in token:
        return False
    if "language" in token or name == "ui_lang":
        return "Zh"
    return p.get("example_input", p.get("parameter_default", p.get("default")))


def build_payload(info, mode, ref_path):
    return [param_value(p, mode, ref_path) for p in (info.get("parameters") or [])]


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


def validate_audio(result, output_dir, slug):
    print(f"Result type={type(result).__name__}: {result!r}", flush=True)
    audio_path = extract_audio_path(result)
    if not audio_path:
        raise RuntimeError("no local audio file returned")
    size = audio_path.stat().st_size
    print(f"Audio path={audio_path} size={size}", flush=True)
    if size < 5000:
        raise RuntimeError(f"audio too small ({size} bytes)")
    target = output_dir / f"cosyvoice-smoke-{slug}.wav"
    shutil.copyfile(audio_path, target)
    print(f"PASS: {target} ({target.stat().st_size} bytes)", flush=True)
    return target


def call_from_api(client, api, mode, ref_path, output_dir, slug):
    candidates = endpoint_candidates(api, mode)
    if not candidates:
        raise RuntimeError("no API endpoints exposed")
    errors = []
    for score, key, info, named in candidates[:8]:
        if score < 30:
            continue
        endpoint = key if named else (int(key) if str(key).isdigit() else key)
        payload = build_payload(info, mode, ref_path)
        print(f"Trying endpoint={endpoint!r} score={score} params={[label_text(p) for p in info.get('parameters') or []]}", flush=True)
        try:
            if named:
                result = client.predict(*payload, api_name=endpoint)
            else:
                result = client.predict(*payload, fn_index=endpoint)
            return validate_audio(result, output_dir, slug)
        except Exception as exc:
            msg = f"{endpoint}: {type(exc).__name__}: {exc}"
            errors.append(msg)
            print(msg, flush=True)
    raise RuntimeError("; ".join(errors) or "all candidate endpoints failed")


def http_diagnostics(base):
    print(f"\nHTTP diagnostics for {base}", flush=True)
    for suffix in ("", "config", "gradio_api/info", "api/info", "gradio_api/openapi.json"):
        url = base.rstrip("/") + ("/" + suffix if suffix else "/")
        try:
            r = requests.get(url, timeout=20, allow_redirects=True)
            ctype = r.headers.get("content-type", "")
            sample = r.text[:1600].replace("\n", " ") if "text" in ctype or "json" in ctype else "<binary>"
            print(f"GET {url} -> {r.status_code} final={r.url} type={ctype} len={len(r.content)} sample={sample}", flush=True)
        except Exception as exc:
            print(f"GET {url} -> {type(exc).__name__}: {exc}", flush=True)


def test_modelscope(base, ref_path, output_dir):
    print(f"\n=== TEST ModelScope dedicated CosyVoice API: {base} ===", flush=True)
    http_diagnostics(base)
    client = Client(base, verbose=True)
    api = client.view_api(return_format="dict")
    print(json.dumps(api, ensure_ascii=False, indent=2)[:30000], flush=True)
    try:
        return call_from_api(client, api, "instruct", ref_path, output_dir, "modelscope-official")
    except Exception as first:
        print(f"ModelScope instruct path failed: {first}", flush=True)
        return call_from_api(client, api, "zero-shot", ref_path, output_dir, "modelscope-official-zero-shot")


def test_hf(space_id, mode, ref_path, output_dir):
    print(f"\n=== DIAGNOSTIC HF TEST {space_id} ({mode}) ===", flush=True)
    client = Client(space_id, verbose=True)
    api = client.view_api(return_format="dict")
    print(json.dumps(api, ensure_ascii=False, indent=2)[:20000], flush=True)
    return call_from_api(client, api, mode, ref_path, output_dir, space_id.split("/")[-1])


def main():
    output_dir = Path("artifacts/cosyvoice-smoke")
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        ref_path = prepare_reference(Path(td))
        errors = []

        for base in MODELSCOPE_BASES:
            try:
                path = test_modelscope(base, ref_path, output_dir)
                print(f"\nCOSYVOICE_SMOKE_PASS={path}", flush=True)
                return 0
            except Exception as exc:
                msg = f"ModelScope {base}: {type(exc).__name__}: {exc}"
                errors.append(msg)
                print(f"FAIL {msg}", flush=True)

        for space_id, mode in HF_DIAGNOSTICS:
            try:
                path = test_hf(space_id, mode, ref_path, output_dir)
                print(f"\nCOSYVOICE_SMOKE_PASS={path}", flush=True)
                return 0
            except Exception as exc:
                msg = f"{space_id}: {type(exc).__name__}: {exc}"
                errors.append(msg)
                print(f"FAIL {msg}", flush=True)

        print("\nALL COSYVOICE BACKENDS FAILED", flush=True)
        for err in errors:
            print(f" - {err}", flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
