#!/usr/bin/env python3
"""Priority Traditional-Chinese speech overrides for World and Asia.

The base table remains in tts_hktrad.py. These additions close the residual
World/Asia audit findings using Hong Kong forms where available, with a
Traditional-Chinese fallback for names without a stable HK newsroom form.
"""
import re
import tts_hktrad as base

OVERRIDES = [
    ("Scott Bessent", "貝森特"),
    ("Masoud Pezeshkian", "佩澤希齊揚"),
    ("Zelenskyy", "澤連斯基"),
    ("Pezeshkian", "佩澤希齊揚"),
    ("Bessent", "貝森特"),
    ("Tanintharyi", "德林達依"),
    ("Dawei", "土瓦"),
    ("Odisha", "奧里薩邦"),
    ("Paradip", "帕拉迪普"),
    ("Jones", "鍾斯"),
    ("Scott", "斯科特"),
    ("Masoud", "馬蘇德"),
    ("AP", "美聯社"),
    ("warrant", "認股權證"),
]


def _replace(text, source, target):
    return re.sub(
        r"(?<![A-Za-z0-9])" + re.escape(source) + r"(?![A-Za-z0-9])",
        target,
        text,
        flags=re.IGNORECASE,
    )


def localize(text):
    out = base.localize(text)
    for source, target in sorted(OVERRIDES, key=lambda item: len(item[0]), reverse=True):
        out = _replace(out, source, target)
    return out


def residual_latin_tokens(text):
    localized = localize(text)
    return sorted({m.group(1) for m in base.LATIN_TOKEN_RE.finditer(localized)}, key=str.lower)


def has_residual_latin(text):
    return bool(residual_latin_tokens(text))
