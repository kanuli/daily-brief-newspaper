#!/usr/bin/env python3
from pathlib import Path

publish = Path('.github/workflows/cosyvoice-publish.yml').read_text(encoding='utf-8')
pages = Path('.github/workflows/pages.yml').read_text(encoding='utf-8')
tts = Path('assets/js/site-tts-v5.js').read_text(encoding='utf-8')
shard_generator = Path('scripts/generate_cosyvoice_shard.py')
article_publisher = Path('scripts/publish_cosyvoice_article.py')
manifest = Path('data/tts-manifest.json')
wave = Path('assets/audio/cosyvoice/latest-lead.wav')

required_publish = [
    'contents: write',
    'generate_cosyvoice_shard.py',
    'publish_cosyvoice_article.py',
    'COSY_SHARD_ONE_ARTICLE: "1"',
    'COSY_SHARD_STABLE_SLOT: "1"',
    'max-parallel: 10',
    'matrix:',
    'slot: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]',
    'for cycle in $(seq 1 12)',
    'git push origin HEAD:main',
    'COSYVOICE_ONE_ARTICLE_MAIN_PUSH_PASS',
    'cancel-in-progress: true',
]
for token in required_publish:
    assert token in publish, f'missing continuous immediate F01 publisher contract token: {token}'

assert 'merge-and-publish:' not in publish, 'production F01 must not wait for a batch merge gate'
assert 'needs: generate-shards' not in publish, 'production F01 must not wait for every generator before publishing'
assert shard_generator.exists(), 'per-article F01 generator missing'
assert article_publisher.exists(), 'immediate F01 article publisher missing'
assert manifest.exists(), 'production tts manifest missing from branch'
assert wave.exists() and wave.stat().st_size > 50000, 'production CosyVoice WAV missing/too small'

generator_text = shard_generator.read_text(encoding='utf-8')
for token in ('STABLE_SLOT', 'one-article-stable-worker-lane', 'stable_slot(story)'):
    assert token in generator_text, f'stable worker-lane generator missing token: {token}'

for token in ('actions/configure-pages@v5', 'actions/upload-pages-artifact@v3', 'actions/deploy-pages@v4', 'cancel-in-progress: true'):
    assert token in pages, f'Pages workflow missing immediate deployment token: {token}'
assert 'paths-ignore:' not in pages, 'Pages must deploy hourly news and every completed F01 commit immediately'
assert 'ref: main' in pages, 'Pages deployment must always package newest cumulative main state'

publisher_text = article_publisher.read_text(encoding='utf-8')
for token in (
    'progressive-current-news-f01-only',
    'per-article-immediate-10-way',
    'pendingArticleCount',
    'COSYVOICE_IMMEDIATE_PUBLISH_PASS',
):
    assert token in publisher_text, f'immediate article publisher missing token: {token}'

assert 'speechSynthesis' not in tts, 'device/browser TTS fallback is forbidden; every playable story must use CosyVoice2-Yue F01'
assert 'SpeechSynthesisUtterance' not in tts, 'browser speech synthesis fallback is forbidden'
assert 'F01 音訊準備中' in tts, 'missing explicit F01 pending state for not-yet-generated stories'
assert 'F01 female reference' in tts, 'front-end must verify/use F01 female reference'
print('COSYVOICE_F01_10_WORKER_IMMEDIATE_CONTRACT_PASS')
