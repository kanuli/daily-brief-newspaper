#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
RAW = "https://raw.githubusercontent.com/kanuli/daily-brief-newspaper/main/data/tts-manifest.json"
VERSION = "20260823-1405rawmanifest"

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

# A promotion failure must never skip all 10 synthesis workers. Promotion is an
# optimization; current-news generation is the recovery path and must still run.
workflow = ROOT / ".github/workflows/cosyvoice-publish.yml"
text = workflow.read_text(encoding="utf-8")
old = "  worker:\n    needs: promote-prebuilt\n    runs-on: ubuntu-latest"
new = "  worker:\n    needs: [ensure-release, promote-prebuilt]\n    if: ${{ always() && needs.ensure-release.result == 'success' }}\n    runs-on: ubuntu-latest"
if old in text:
    text = text.replace(old, new)
elif new not in text:
    raise SystemExit("cosyvoice worker dependency marker not found")
workflow.write_text(text, encoding="utf-8")
print("updated .github/workflows/cosyvoice-publish.yml")
