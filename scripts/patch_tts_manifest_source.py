#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/kanuli/daily-brief-newspaper/main/data/tts-manifest.json"
VERSION = "20260823-1355rawmanifest"

replacements = {
    ROOT / "assets/js/site-tts-v5.js": [
        ('const MANIFEST_URL = "data/tts-manifest.json";', f'const MANIFEST_URL = "{RAW}";'),
    ],
    ROOT / "assets/js/voice-production-status.js": [
        ('const MANIFEST_PATH = "data/tts-manifest.json";', f'const MANIFEST_PATH = "{RAW}";'),
    ],
}

for path, pairs in replacements.items():
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in pairs:
        if old not in text and new not in text:
            raise SystemExit(f"expected marker missing in {path}: {old}")
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print("updated", path.relative_to(ROOT))

system = ROOT / "assets/js/system-panel.js"
text = system.read_text(encoding="utf-8")
text = re.sub(r'assets/js/site-tts-v5\.js\?v=[^\"]+', f'assets/js/site-tts-v5.js?v={VERSION}', text)
text = re.sub(r'assets/js/voice-production-status\.js\?v=[^\"]+', f'assets/js/voice-production-status.js?v={VERSION}', text)
system.write_text(text, encoding="utf-8")
print("updated assets/js/system-panel.js")

for path in ROOT.glob("*.html"):
    text = path.read_text(encoding="utf-8")
    new = re.sub(r'assets/js/system-panel\.js\?v=[^\"\']+', f'assets/js/system-panel.js?v={VERSION}', text)
    new = re.sub(r'assets/js/voice-production-status\.js\?v=[^\"\']+', f'assets/js/voice-production-status.js?v={VERSION}', new)
    new = re.sub(r'assets/js/site-tts-v5\.js\?v=[^\"\']+', f'assets/js/site-tts-v5.js?v={VERSION}', new)
    if new != text:
        path.write_text(new, encoding="utf-8")
        print("cache-bust", path.name)
