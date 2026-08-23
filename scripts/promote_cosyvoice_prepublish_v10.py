#!/usr/bin/env python3
"""Promote only current-policy prebuilt F01 assets with salted content identity."""
import hashlib

import cosyvoice_policy as policy
import promote_cosyvoice_prepublish_anchor as anchor

_original_content_sha = anchor.legacy.content_sha


def _salted_content_sha(story):
    base = _original_content_sha(story)
    return hashlib.sha256(f"{policy.POLICY}\0{base}".encode("utf-8")).hexdigest()


anchor.legacy.content_sha = _salted_content_sha

if __name__ == "__main__":
    code = anchor.legacy.main()
    anchor._stamp_manifest()
    raise SystemExit(code)
