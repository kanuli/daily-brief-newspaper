#!/usr/bin/env python3
"""Single source of truth for the production Cantonese news voice policy."""

POLICY = "f01-news-anchor-v14-young-female-semantic-sentences-hktrad"
ASSET_NAMESPACE = "v14"
REFERENCE_POLICY = "aslp-approved-databaker-female-synthetic-v1"
REFERENCE_ASSET = "9f24c7f95a2d040c43ce9fadfa56f6f3.wav"
REFERENCE_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/9f24c7f95a2d040c43ce9fadfa56f6f3.wav"
REFERENCE_START_SECONDS = 0.0
REFERENCE_DURATION_SECONDS = 8.0
INITIAL_CONDITIONING_POLICY = "approved-young-female-synthetic-per-semantic-sentence"
LANGUAGE_GATE = "residual-latin-zero"
SEGMENT_POLICY = "semantic-sentence-reference-locked"
INFERENCE_MODE = "cross-lingual-reference-only-per-semantic-sentence"

# Preserve the young female voice already accepted by the user. The final
# reliability attempt changes delivery architecture only: short semantically
# complete Cantonese segments, each generated against the same reference.
VOICE_SPEED = 1.0
PACING_POLICY = "hk-tv-news-semantic-pauses-v3-conservative"
PACING_TARGET = "RYTsc9N5748@04:19-05:00"
TEMPO_POLICY = "model-speed-only-no-post-stretch"

# Anchor timing: comma ~= half beat; full stop ~= full beat. These are silence
# joins between complete semantic segments, not characters injected into text.
COMMA_PAUSE_SECONDS = 0.18
SEMICOLON_PAUSE_SECONDS = 0.30
FULL_STOP_PAUSE_SECONDS = 0.38
QUESTION_PAUSE_SECONDS = 0.42
MAX_SEMANTIC_SEGMENT_CHARS = 34
MIN_SEMANTIC_SEGMENT_CHARS = 7
