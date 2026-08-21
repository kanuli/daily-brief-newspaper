#!/usr/bin/env python3
from pathlib import Path

publish = Path('.github/workflows/cosyvoice-publish.yml').read_text(encoding='utf-8')
pages = Path('.github/workflows/pages.yml').read_text(encoding='utf-8')
manifest = Path('data/tts-manifest.json')
wave = Path('assets/audio/cosyvoice/latest-lead.wav')

required = [
    'pages: write',
    'id-token: write',
    'actions/configure-pages@v5',
    'actions/upload-pages-artifact@v3',
    'actions/deploy-pages@v4',
]
for token in required:
    assert token in publish, f'missing CosyVoice Pages contract token: {token}'

assert 'path: .' in publish, 'CosyVoice publisher must upload the full static site'
assert manifest.exists(), 'production tts manifest missing from branch'
assert wave.exists() and wave.stat().st_size > 50000, 'production CosyVoice WAV missing/too small'
assert 'actions/deploy-pages@v4' in pages, 'normal Pages workflow missing deploy-pages'
print('COSYVOICE_PAGES_CONTRACT_PASS')
