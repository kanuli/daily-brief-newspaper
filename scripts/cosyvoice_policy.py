#!/usr/bin/env python3
"""Single source of truth for the production F01 voice policy."""

POLICY = "f01-news-anchor-v10-cache-isolated-semantic-pauses-approved-10s-hktrad"
ASSET_NAMESPACE = "v10"
REFERENCE_POLICY = "user-approved-nvidia-anchor-v1"
REFERENCE_ASSET = "ai-nvidia-server-price-0800-79489f0afc38.wav"
REFERENCE_START_SECONDS = 10.0
REFERENCE_DURATION_SECONDS = 10.0
INITIAL_CONDITIONING_POLICY = "approved-reference-bistream"
LANGUAGE_GATE = "residual-latin-zero"
SEGMENT_POLICY = "single-inference-per-article"
INFERENCE_MODE = "cross-lingual-reference-only"

# Keep speaker speed native while semantic punctuation controls cadence. The
# user supplied YouTube clip is the target reference, but its 04:19-05:00 audio
# cannot be measured reliably from CI, so do not invent an artificial numeric
# speed match. Any later calibrated speed change belongs here, not in audio
# post-processing.
VOICE_SPEED = 1.0
PACING_POLICY = "hk-tv-news-semantic-pauses-v1"
TEMPO_POLICY = "model-speed-only-no-post-stretch"
MICRO_PAUSE_MARK = "，"
DISTINCT_PAUSE_MARK = "；"
FULL_PAUSE_MARK = "。"
