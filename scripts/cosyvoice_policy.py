#!/usr/bin/env python3
"""Single source of truth for the production F01 voice policy."""

POLICY = "f01-news-anchor-v13-approved-young-female-hk-pacing-hktrad"
ASSET_NAMESPACE = "v13"
REFERENCE_POLICY = "aslp-approved-databaker-female-synthetic-v1"
REFERENCE_ASSET = "9f24c7f95a2d040c43ce9fadfa56f6f3.wav"
REFERENCE_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/9f24c7f95a2d040c43ce9fadfa56f6f3.wav"
REFERENCE_START_SECONDS = 0.0
REFERENCE_DURATION_SECONDS = 8.0
INITIAL_CONDITIONING_POLICY = "approved-young-female-synthetic-bistream"
LANGUAGE_GATE = "residual-latin-zero"
SEGMENT_POLICY = "single-inference-per-article"
INFERENCE_MODE = "cross-lingual-reference-only"

# This is the actual official CosyVoice2-Yue-Databaker female synthetic sample
# the user selected during the original A/B test. Use that approved young female
# output as the speaker-conditioning source; do not substitute the raw F01
# recording or a recursively generated news WAV. Keep native speed 1.0 and the
# user's HK TV-news semantic pacing so this revision isolates speaker identity.
VOICE_SPEED = 1.0
PACING_POLICY = "hk-tv-news-semantic-pauses-v2"
PACING_TARGET = "RYTsc9N5748@04:19-05:00"
TEMPO_POLICY = "model-speed-only-no-post-stretch"
MICRO_PAUSE_MARK = "，"
DISTINCT_PAUSE_MARK = "；"
FULL_PAUSE_MARK = "。"
