#!/usr/bin/env python3
"""Hong Kong mixed Cantonese-English speech terminology policy.

This layer sits in front of the older speech localization tables.  It protects
brand/product/technical names that Hong Kong newsrooms and Cantonese speakers
normally keep in English, while still allowing the established Chinese names
from v2 for entities such as 微軟、聯儲局、曼聯、阿仙奴、彭博等.

Unknown English is preserved by default.  We do not invent a Chinese literal
translation solely to satisfy TTS because canto-tts-nano explicitly supports
Cantonese + English code-switching.
"""
from __future__ import annotations

import re

import tts_hktrad_v2 as legacy

# High-confidence Hong Kong English usage.  Longest match wins.  This list is
# intentionally conservative: anything not listed is still allowed to remain
# English unless an older table contains a genuinely established HK Chinese
# name for it.
PRESERVE_OFFICIAL_ENGLISH = (
    "Super Micro Computer",
    "Digital Markets Act",
    "OpenAI",
    "ChatGPT",
    "Google",
    "NVIDIA",
    "Nvidia",
    "Meta",
    "iPhone",
    "Android",
    "App Store",
    "Apple Watch",
    "AirPods",
    "Perplexity",
    "Palantir",
    "Marvell",
    "Copilot",
    "Azure",
    "Gemini",
    "Blackwell",
    "Alphabet",
    "AAPL",
    "GOOG",
    "NVDA",
    "DRAM",
    "HBM",
    "TPU",
    "RPO",
    "IAP",
    "DSX",
    "GPU",
    "CPU",
    "API",
    "ETF",
    "IPO",
    "GDP",
    "CPI",
    "PPI",
    "AI",
)

# These literal translations are specifically rejected because they are not
# normal Hong Kong naming and distort the identity of the product/company.
FORBIDDEN_LITERAL_TRANSLATIONS = {
    "OpenAI": "開放人工智能公司",
    "ChatGPT": "人工智能聊天機械人",
}

LATIN_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9.+&'’/-]*)(?![A-Za-z0-9])"
)


def _protect(text: str):
    out = str(text or "")
    restored = {}
    next_code = 0xE000
    for term in sorted(PRESERVE_OFFICIAL_ENGLISH, key=len, reverse=True):
        pattern = re.compile(
            r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])",
            re.IGNORECASE,
        )

        def repl(match):
            nonlocal next_code
            marker = chr(next_code)
            next_code += 1
            restored[marker] = match.group(0)
            return marker

        out = pattern.sub(repl, out)
    return out, restored


def localize(text: str) -> str:
    source = str(text or "")
    protected, restored = _protect(source)
    out = legacy.localize(protected)
    for marker, original in restored.items():
        out = out.replace(marker, original)

    for source_term, bad_translation in FORBIDDEN_LITERAL_TRANSLATIONS.items():
        if re.search(
            r"(?<![A-Za-z0-9])" + re.escape(source_term) + r"(?![A-Za-z0-9])",
            source,
            flags=re.IGNORECASE,
        ) and bad_translation in out:
            raise RuntimeError(
                f"HK terminology gate rejected literal translation: "
                f"{source_term} -> {bad_translation}"
            )
    return out


def residual_latin_tokens(text: str) -> list[str]:
    """Audit English/code-switch tokens; presence is valid and expected."""
    localized = localize(text)
    return sorted(
        {m.group(1) for m in LATIN_TOKEN_RE.finditer(localized)},
        key=str.lower,
    )


def has_residual_latin(text: str) -> bool:
    return bool(residual_latin_tokens(text))
