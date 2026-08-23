#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V3 = "f01-news-anchor-v3-stable-tempo"
V4 = "f01-news-anchor-v4-golden-nvidia"
GOLDEN_ASSET = "ai-nvidia-server-price-0800-79489f0afc38.wav"
GOLDEN_URL = f"https://github.com/kanuli/daily-brief-newspaper/releases/download/f01-voice-cache/{GOLDEN_ASSET}"
REFERENCE_POLICY = "user-approved-nvidia-anchor-v1"
SEED = "20260823"


def replace_once(text, old, new, label):
    if old in text:
        return text.replace(old, new, 1)
    if new in text:
        return text
    raise SystemExit(f"{label}: expected marker missing: {old!r}")


def write(path, text):
    path.write_text(text, encoding="utf-8")
    print("updated", path.relative_to(ROOT))

# Base engine: use the user-approved Nvidia sample as the stable speaker reference,
# crop a consistent 10-second mid-window, and reset the generation RNG per segment.
path = ROOT / "scripts/generate_cosyvoice_lead.py"
text = path.read_text(encoding="utf-8")
text = text.replace('VOICE_POLICY_VERSION = "f01-news-anchor-v2-cross-lingual"', f'VOICE_POLICY_VERSION = "{V4}"')
text = replace_once(
    text,
    'VOICE_SPEED = float(os.environ.get("COSY_VOICE_SPEED", "1.0"))\n',
    'VOICE_SPEED = float(os.environ.get("COSY_VOICE_SPEED", "1.0"))\n'
    f'VOICE_RANDOM_SEED = int(os.environ.get("COSY_VOICE_SEED", "{SEED}"))\n'
    f'VOICE_REFERENCE_POLICY = "{REFERENCE_POLICY}"\n'
    'VOICE_REFERENCE_START_SECONDS = float(os.environ.get("COSY_REFERENCE_START_SECONDS", "10.0"))\n'
    'VOICE_REFERENCE_DURATION_SECONDS = float(os.environ.get("COSY_REFERENCE_DURATION_SECONDS", "10.0"))\n',
    "base constants",
)
old_url_prefix = 'F01_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav"'
text = text.replace(old_url_prefix, f'F01_URL = "{GOLDEN_URL}"')
if "def load_reference_prompt(" not in text:
    marker = "\ndef ensure_model():\n"
    helper = '''\ndef load_reference_prompt(load_wav, ref_path):\n    prompt = load_wav(str(ref_path), 16000)\n    if prompt.ndim != 2 or prompt.shape[1] < 16000 * 4:\n        raise RuntimeError("golden F01 reference is too short")\n    start = int(round(VOICE_REFERENCE_START_SECONDS * 16000))\n    length = int(round(VOICE_REFERENCE_DURATION_SECONDS * 16000))\n    if start + length > prompt.shape[1]:\n        start = max(0, prompt.shape[1] - length)\n    cropped = prompt[:, start:start + length]\n    if cropped.shape[1] < 16000 * 4:\n        raise RuntimeError("golden F01 reference crop is too short")\n    print(\n        f"Using golden F01 reference policy={VOICE_REFERENCE_POLICY} "\n        f"start={start/16000:.2f}s duration={cropped.shape[1]/16000:.2f}s",\n        flush=True,\n    )\n    return cropped\n\n'''
    if marker not in text:
        raise SystemExit("base helper insertion marker missing")
    text = text.replace(marker, helper + marker, 1)
if "torch.manual_seed(VOICE_RANDOM_SEED)" not in text:
    marker = '    chunks = []\n    with torch.inference_mode():\n'
    repl = '    # Reset the stochastic sampler for every segment so speaker age/timbre does not drift.\n    torch.manual_seed(VOICE_RANDOM_SEED)\n    chunks = []\n    with torch.inference_mode():\n'
    text = replace_once(text, marker, repl, "segment seed")
text = text.replace('prompt_speech_16k = load_wav(str(ref), 16000)', 'prompt_speech_16k = load_reference_prompt(load_wav, ref)')
# stamp reference metadata in lead manifests when this path is used directly
text = text.replace('"instructionPolicy": "none-reference-only",\n        "prosodyPolicy": VOICE_POLICY_VERSION,',
                    '"instructionPolicy": "none-reference-only",\n        "referencePolicy": VOICE_REFERENCE_POLICY,\n        "referenceAsset": Path(F01_URL).name,\n        "prosodyPolicy": VOICE_POLICY_VERSION,')
write(path, text)

# All-news/shared setup must use the same cropped reference helper.
path = ROOT / "scripts/generate_cosyvoice_all.py"
text = path.read_text(encoding="utf-8")
text = text.replace('prompt = load_wav(str(ref), 16000)', 'prompt = base.load_reference_prompt(load_wav, ref)')
write(path, text)

# Production stable-tempo wrapper: v4 and only gentle post tempo correction.
path = ROOT / "scripts/generate_cosyvoice_shard_anchor.py"
text = path.read_text(encoding="utf-8")
text = text.replace(V3, V4)
text = text.replace('MIN_TEMPO = 0.88', 'MIN_TEMPO = 0.96')
text = text.replace('MAX_TEMPO = 1.12', 'MAX_TEMPO = 1.04')
if '"referencePolicy": voice_base.VOICE_REFERENCE_POLICY,' not in text:
    text = text.replace('"instructionPolicy": "none-reference-only",\n        "tempoTargetCharsPerSecond": TARGET_CHARS_PER_SECOND,',
                        '"instructionPolicy": "none-reference-only",\n        "referencePolicy": voice_base.VOICE_REFERENCE_POLICY,\n        "referenceAsset": Path(voice_base.F01_URL).name,\n        "tempoTargetCharsPerSecond": TARGET_CHARS_PER_SECOND,')
    if 'from pathlib import Path' not in text:
        text = text.replace('import re\n', 'import re\nfrom pathlib import Path\n', 1)
write(path, text)

# Manifest policy wrappers.
for rel in [
    "scripts/publish_cosyvoice_article_anchor.py",
    "scripts/publish_cosyvoice_prepublish_anchor.py",
]:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8").replace(V3, V4)
    if '"referencePolicy": voice_base.VOICE_REFERENCE_POLICY,' not in text:
        text = text.replace('"instructionPolicy": "none-reference-only",\n        "prosodyPolicy": POLICY,',
                            '"instructionPolicy": "none-reference-only",\n        "referencePolicy": voice_base.VOICE_REFERENCE_POLICY,\n        "referenceAsset": Path(voice_base.F01_URL).name,\n        "prosodyPolicy": POLICY,')
    write(path, text)

path = ROOT / "scripts/promote_cosyvoice_prepublish_anchor.py"
text = path.read_text(encoding="utf-8").replace(V3, V4)
if f'REFERENCE_POLICY = "{REFERENCE_POLICY}"' not in text:
    text = text.replace('VOICE_SPEED = 1.0\n', f'VOICE_SPEED = 1.0\nREFERENCE_POLICY = "{REFERENCE_POLICY}"\nREFERENCE_ASSET = "{GOLDEN_ASSET}"\n', 1)
if '"referencePolicy": REFERENCE_POLICY,' not in text:
    text = text.replace('"instructionPolicy": "none-reference-only",\n        "prosodyPolicy": POLICY,',
                        '"instructionPolicy": "none-reference-only",\n        "referencePolicy": REFERENCE_POLICY,\n        "referenceAsset": REFERENCE_ASSET,\n        "prosodyPolicy": POLICY,')
write(path, text)

# Protect the single golden reference from normal 48h retention and high-water pruning.
for rel in [
    ".github/workflows/cosyvoice-retention.yml",
    ".github/workflows/cosyvoice-capacity-guard.yml",
]:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    text = text.replace('protected = set()', f'protected = {{"{GOLDEN_ASSET}"}}')
    write(path, text)

print(f"GOLDEN_F01_REFERENCE_APPLIED policy={V4} asset={GOLDEN_ASSET}")
