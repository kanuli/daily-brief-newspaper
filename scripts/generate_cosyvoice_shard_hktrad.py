#!/usr/bin/env python3
"""Production F01 shard with Traditional-Chinese speech localization."""
import generate_cosyvoice_shard_anchor as anchor
import tts_hktrad_v2 as hktrad

_original_normalize = anchor.voice_base.normalize_for_tts


def _localized(value):
    return hktrad.localize(_original_normalize(value))


# generate_cosyvoice_all.content_sha and the anchor segment builder reference the
# same generate_cosyvoice_lead module object, so one patch keeps hashing and
# spoken text identical.
anchor.voice_base.normalize_for_tts = _localized

if __name__ == "__main__":
    raise SystemExit(anchor.legacy.main())
