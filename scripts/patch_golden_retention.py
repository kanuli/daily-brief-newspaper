#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = "ai-nvidia-server-price-0800-79489f0afc38.wav"

for rel in [
    ".github/workflows/cosyvoice-retention.yml",
    ".github/workflows/cosyvoice-capacity-guard.yml",
]:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    old = "protected = set()"
    new = f'protected = {{"{GOLDEN}"}}'
    if old in text:
        text = text.replace(old, new, 1)
        path.write_text(text, encoding="utf-8")
        print("protected golden reference in", rel)
    elif new in text:
        print("already protected in", rel)
    else:
        raise SystemExit(f"cannot locate protected set in {rel}")
