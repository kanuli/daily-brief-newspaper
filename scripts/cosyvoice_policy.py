#!/usr/bin/env python3
"""Single source of truth for the production F01 voice policy."""

POLICY = "f01-news-anchor-v12-official-f01-neutral-hk-pacing-hktrad"
ASSET_NAMESPACE = "v12"
REFERENCE_POLICY = "aslp-official-f01-neutral-20054-v1"
REFERENCE_ASSET = "F01_中立_20054.wav"
REFERENCE_URL = "https://raw.githubusercontent.com/ASLP-lab/WenetSpeech-Yue/demo_page/raw/TTS_samples/F01_%E4%B8%AD%E7%AB%8B_20054.wav"
REFERENCE_START_SECONDS = 0.0
REFERENCE_DURATION_SECONDS = 8.0
INITIAL_CONDITIONING_POLICY = "official-f01-neutral-bistream"
LANGUAGE_GATE = "residual-latin-zero"
SEGMENT_POLICY = "single-inference-per-article"
INFERENCE_MODE = "cross-lingual-reference-only"

# Use the original official F01 neutral female reference that the first working
# integration used. Keep the user's Hong Kong TV-news clip as a pacing target
# only; do not clone that anchor's identity. Native speed is restored to 1.0 so
# the voice is not artificially thickened/aged by slow synthesis.
VOICE_SPEED = 1.0
PACING_POLICY = "hk-tv-news-semantic-pauses-v2"
PACING_TARGET = "RYTsc9N5748@04:19-05:00"
TEMPO_POLICY = "model-speed-only-no-post-stretch"
MICRO_PAUSE_MARK = "，"
DISTINCT_PAUSE_MARK = "；"
FULL_PAUSE_MARK = "。"
