#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_POLICIES = ["f01-news-anchor-v3-stable-tempo", "f01-news-anchor-v4-golden-nvidia"]
NEW_POLICY = "f01-news-anchor-v5-golden-hktrad"


def patch(path, transform):
    text = path.read_text(encoding="utf-8")
    new = transform(text)
    if new != text:
        path.write_text(new, encoding="utf-8")
        print("updated", path.relative_to(ROOT))
    else:
        print("unchanged", path.relative_to(ROOT))


def patch_base(text):
    if "import tts_hktrad" not in text:
        marker = "from huggingface_hub import snapshot_download\n"
        if marker not in text:
            raise SystemExit("generate_cosyvoice_lead.py import marker missing")
        text = text.replace(marker, marker + "\nimport tts_hktrad\n", 1)
    marker = "def normalize_for_tts(value):\n    text = clean_text(value)\n"
    replacement = "def normalize_for_tts(value):\n    text = tts_hktrad.localize(clean_text(value))\n"
    if marker in text:
        text = text.replace(marker, replacement, 1)
    elif replacement not in text:
        raise SystemExit("generate_cosyvoice_lead.py normalize marker missing")
    return text


patch(ROOT / "scripts/generate_cosyvoice_lead.py", patch_base)

for rel in [
    "scripts/generate_cosyvoice_shard_anchor.py",
    "scripts/publish_cosyvoice_article_anchor.py",
    "scripts/publish_cosyvoice_prepublish_anchor.py",
    "scripts/promote_cosyvoice_prepublish_anchor.py",
]:
    def do(text, rel=rel):
        for old in OLD_POLICIES:
            text = text.replace(old, NEW_POLICY)
        return text
    patch(ROOT / rel, do)

print("TTS_HKTRAD_MIGRATION_PASS policy=" + NEW_POLICY)
