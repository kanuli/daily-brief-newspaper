#!/usr/bin/env python3
import os
import sys
import time
import urllib.request
from pathlib import Path

import torch
import torchaudio
from huggingface_hub import snapshot_download

TEST_TEXT = "今日香港天氣很好。這是一段廣東話語音測試。"
INSTRUCT = "用粤语说这句话"
F01_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav"
REPO_ROOT = Path(os.environ.get("WSYUE_ROOT", "/tmp/WenetSpeech-Yue"))
CODE_ROOT = REPO_ROOT / "CosyVoice2-Yue"
MODEL_DIR = Path(os.environ.get("COSY_MODEL_DIR", "/tmp/Cosyvoice2-Yue"))
OUTPUT = Path("artifacts/cosyvoice-smoke/cosyvoice2-yue-local-cpu.wav")


def main():
    print("=== OFFICIAL LOCAL CPU COSYVOICE2-YUE E2E ===", flush=True)
    print(f"torch={torch.__version__} cuda={torch.cuda.is_available()}", flush=True)
    print(f"code={CODE_ROOT}", flush=True)
    if not CODE_ROOT.exists():
        raise RuntimeError(f"WenetSpeech-Yue code not found: {CODE_ROOT}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading only CPU-required ASLP-lab/Cosyvoice2-Yue files...", flush=True)
    t0 = time.time()
    snapshot_download(
        repo_id="ASLP-lab/Cosyvoice2-Yue",
        local_dir=str(MODEL_DIR),
        allow_patterns=[
            "cosyvoice2.yaml",
            "configuration.json",
            "campplus.onnx",
            "speech_tokenizer_v2.onnx",
            "spk2info.pt",
            "llm.pt",
            "flow.pt",
            "hift.pt",
            "CosyVoice-BlankEN/*",
        ],
    )
    print(f"Model download complete in {time.time() - t0:.1f}s", flush=True)
    for path in sorted(MODEL_DIR.rglob("*")):
        if path.is_file():
            print(f"MODEL_FILE {path.relative_to(MODEL_DIR)} {path.stat().st_size}", flush=True)

    sys.path.insert(0, str(CODE_ROOT))
    sys.path.insert(0, str(CODE_ROOT / "third_party" / "Matcha-TTS"))

    from cosyvoice.cli.cosyvoice import CosyVoice2
    from cosyvoice.utils.file_utils import load_wav

    ref = Path("/tmp/F01_female.wav")
    urllib.request.urlretrieve(F01_URL, ref)
    print(f"F01 reference bytes={ref.stat().st_size}", flush=True)

    print("Loading CosyVoice2-Yue on CPU...", flush=True)
    t1 = time.time()
    cosyvoice = CosyVoice2(
        str(MODEL_DIR),
        load_jit=False,
        load_trt=False,
        load_vllm=False,
        fp16=False,
    )
    print(f"Model loaded in {time.time() - t1:.1f}s sample_rate={cosyvoice.sample_rate}", flush=True)

    prompt_speech_16k = load_wav(str(ref), 16000)
    chunks = []
    print(f"Synthesizing: {TEST_TEXT}", flush=True)
    t2 = time.time()
    with torch.inference_mode():
        for idx, result in enumerate(
            cosyvoice.inference_instruct2(
                TEST_TEXT,
                INSTRUCT,
                prompt_speech_16k,
                stream=False,
            )
        ):
            speech = result["tts_speech"].detach().cpu()
            print(f"chunk={idx} shape={tuple(speech.shape)}", flush=True)
            chunks.append(speech)

    if not chunks:
        raise RuntimeError("CosyVoice2-Yue returned zero audio chunks")

    speech = torch.cat(chunks, dim=1)
    duration = speech.shape[1] / cosyvoice.sample_rate
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(str(OUTPUT), speech, cosyvoice.sample_rate, backend="soundfile")
    size = OUTPUT.stat().st_size
    elapsed = time.time() - t2
    print(f"Generated duration={duration:.3f}s bytes={size} inference_seconds={elapsed:.1f}", flush=True)

    if duration < 0.5:
        raise RuntimeError(f"generated audio too short: {duration:.3f}s")
    if size < 10000:
        raise RuntimeError(f"generated WAV too small: {size} bytes")

    print(f"COSYVOICE_LOCAL_CPU_PASS={OUTPUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
