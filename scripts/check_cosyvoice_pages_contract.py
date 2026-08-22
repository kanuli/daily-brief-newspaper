#!/usr/bin/env python3
from pathlib import Path

publish = Path('.github/workflows/cosyvoice-publish.yml').read_text(encoding='utf-8')
pages = Path('.github/workflows/pages.yml').read_text(encoding='utf-8')
tts = Path('assets/js/site-tts-v5.js').read_text(encoding='utf-8')
all_generator = Path('scripts/generate_cosyvoice_all.py')
manifest = Path('data/tts-manifest.json')
wave = Path('assets/audio/cosyvoice/latest-lead.wav')

required_publish = [
    'pages: write',
    'id-token: write',
    'actions/configure-pages@v5',
    'actions/upload-pages-artifact@v3',
    'actions/deploy-pages@v4',
    'generate_cosyvoice_all.py',
    'COSYVOICE_ALL_NEWS_MANIFEST_PASS',
    'cancel-in-progress: false',
    'coveragePolicy',
]
for token in required_publish:
    assert token in publish, f'missing all-news F01 publisher contract token: {token}'

assert 'path: .' in publish, 'F01 publisher must upload the full static site'
assert all_generator.exists(), 'all-news F01 generator missing'
assert manifest.exists(), 'production tts manifest missing from branch'
assert wave.exists() and wave.stat().st_size > 50000, 'production CosyVoice WAV missing/too small'
assert 'actions/deploy-pages@v4' in pages, 'normal Pages workflow missing deploy-pages'
for path_token in ('data/latest.json', 'data/live.json', 'data/desk-latest.json', 'data/stocks-latest.json', 'assets/audio/cosyvoice/**'):
    assert path_token in pages, f'Pages workflow must defer {path_token} to the F01 publisher'

assert 'speechSynthesis' not in tts, 'device/browser TTS fallback is forbidden; every playable story must use CosyVoice2-Yue F01'
assert 'SpeechSynthesisUtterance' not in tts, 'browser speech synthesis fallback is forbidden'
assert 'F01 音訊準備中' in tts, 'missing explicit F01 pending state for not-yet-generated stories'
assert 'F01 female reference' in tts, 'front-end must verify/use F01 female reference'
print('COSYVOICE_F01_ALL_NEWS_CONTRACT_PASS')
