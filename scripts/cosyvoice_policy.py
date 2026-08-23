#!/usr/bin/env python3
"""Single source of truth for the production F01 voice policy."""

POLICY = "f01-news-anchor-v8-approved-10s-bistream-hktrad"
REFERENCE_POLICY = "user-approved-nvidia-anchor-v1"
REFERENCE_ASSET = "ai-nvidia-server-price-0800-79489f0afc38.wav"
REFERENCE_START_SECONDS = 10.0
REFERENCE_DURATION_SECONDS = 10.0
INITIAL_CONDITIONING_POLICY = "approved-reference-bistream"
LANGUAGE_GATE = "residual-latin-zero"
SEGMENT_POLICY = "single-inference-per-article"
INFERENCE_MODE = "cross-lingual-reference-only"
VOICE_SPEED = 1.0
