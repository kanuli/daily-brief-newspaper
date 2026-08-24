#!/usr/bin/env python3
"""Single source of truth for the production F01 voice policy."""

POLICY = "f01-news-anchor-v11-hk-anchor-paced-approved-10s-hktrad"
ASSET_NAMESPACE = "v11"
REFERENCE_POLICY = "user-approved-nvidia-anchor-v1"
REFERENCE_ASSET = "ai-nvidia-server-price-0800-79489f0afc38.wav"
REFERENCE_START_SECONDS = 10.0
REFERENCE_DURATION_SECONDS = 10.0
INITIAL_CONDITIONING_POLICY = "approved-reference-bistream"
LANGUAGE_GATE = "residual-latin-zero"
SEGMENT_POLICY = "single-inference-per-article"
INFERENCE_MODE = "cross-lingual-reference-only"

# The user-supplied Hong Kong Cantonese news clip RYTsc9N5748 (04:19-05:00)
# is a delivery/pacing target only. Keep the approved F01 female identity and
# make the target audible through native model speed plus semantic punctuation;
# do not clone the source anchor's identity and do not post-stretch the WAV.
VOICE_SPEED = 0.92
PACING_POLICY = "hk-tv-news-semantic-pauses-v2"
PACING_TARGET = "RYTsc9N5748@04:19-05:00"
TEMPO_POLICY = "model-speed-only-no-post-stretch"
MICRO_PAUSE_MARK = "，"
DISTINCT_PAUSE_MARK = "；"
FULL_PAUSE_MARK = "。"
