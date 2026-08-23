#!/usr/bin/env python3
"""Bind F01 content and asset identity to the current voice policy.

This prevents a newly generated voice policy from overwriting an older GitHub
Release asset at the same URL. Every policy therefore gets a distinct digest
and WAV filename even when the visible article text is unchanged.
"""
import hashlib

import cosyvoice_policy as policy


def install(gen):
    if getattr(gen, "_cosyvoice_cache_identity_installed", False):
        return gen

    original_content_sha = gen.content_sha

    def policy_content_sha(story):
        base_digest = original_content_sha(story)
        payload = f"{policy.POLICY}\0{base_digest}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def policy_target_path(story, digest):
        return gen.AUDIO_DIR / f"{gen.story_identity(story)}-{policy.ASSET_NAMESPACE}-{digest[:12]}.wav"

    gen.content_sha = policy_content_sha
    gen.target_path = policy_target_path
    gen._cosyvoice_cache_identity_installed = True
    return gen


def salted_digest_from_base(base_digest):
    payload = f"{policy.POLICY}\0{base_digest}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
