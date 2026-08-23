#!/usr/bin/env python3
"""Technical-unit localization shared by display, audit and Cantonese TTS."""
import re

# Unit tokens may be attached directly to digits (for example 2nm), so these
# deliberately use alphabetic rather than alphanumeric boundaries.
UNIT_REPLACEMENTS = [
    ("nm", "納米"),
]


def localize_units(text):
    out = str(text or "")
    for source, target in sorted(UNIT_REPLACEMENTS, key=lambda item: len(item[0]), reverse=True):
        out = re.sub(
            r"(?<![A-Za-z])" + re.escape(source) + r"(?![A-Za-z])",
            target,
            out,
            flags=re.IGNORECASE,
        )
    return out
