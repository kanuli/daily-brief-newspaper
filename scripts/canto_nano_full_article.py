#!/usr/bin/env python3
"""Run canto-nano production with full visible-article TTS coverage.

This wrapper deliberately removes silent article/body truncation from the legacy
production module. It also verifies that semantic-unit segmentation preserves
the complete selected script before a WAV can be published.
"""
from __future__ import annotations

import re

import canto_nano_prod as base

COVERAGE_POLICY = "full-visible-article-no-truncation-v1"

# The Cantonese production model is intentionally protected from raw Latin
# tokens. Existing Hong Kong/localized names are handled by tts_hktrad first;
# any uncommon proper name or acronym left over is read deterministically as
# letters instead of causing the whole article to fail or being deleted.
LETTER_NAMES = {
    "A": "欸", "B": "比", "C": "施", "D": "啲", "E": "伊", "F": "艾夫",
    "G": "芝", "H": "艾治", "I": "艾", "J": "啫", "K": "基", "L": "艾路",
    "M": "艾姆", "N": "艾恩", "O": "柯", "P": "披", "Q": "翹", "R": "亞",
    "S": "艾斯", "T": "剔", "U": "優", "V": "維", "W": "打孖優",
    "X": "艾克斯", "Y": "歪", "Z": "些德",
}
LATIN_WORD_RE = re.compile(r"[A-Za-z]+")


def pronounce_residual_latin(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(0)
        return "、".join(LETTER_NAMES[ch.upper()] for ch in token)
    return LATIN_WORD_RE.sub(repl, text)


def full_script(story):
    values = []
    seen = set()

    def add(value):
        value = base.clean(value)
        if value and value not in seen:
            seen.add(value)
            values.append(value)

    add(story.get("title"))
    add(story.get("dek"))
    add(story.get("summary"))

    # Every body paragraph is visible on the article page, so every paragraph
    # must be included in the spoken version as well.
    for paragraph in [
        base.clean(x)
        for x in re.split(r"\n\s*\n", str(story.get("body") or ""))
        if base.clean(x)
    ]:
        add(paragraph)

    add(story.get("context") or story.get("background"))
    add(story.get("why") or story.get("whyImportant"))
    add(story.get("watchNext") or story.get("nextStep"))

    out = []
    for raw in values:
        text = base.hktrad.localize(raw)
        # Do not throw away an otherwise complete article merely because an
        # uncommon source/proper name was not in the localization dictionary.
        # Spell the remaining Latin token so every visible fact is still read.
        if base.hktrad.residual_latin_tokens(text):
            text = pronounce_residual_latin(text)
        if text and text[-1] not in "。！？!?":
            text += "。"
        out.append(text)

    script = "".join(out)
    if base.LIMIT > 0 and len(script) > base.LIMIT:
        raise RuntimeError(
            f"article exceeds configured TTS guard: {len(script)}>{base.LIMIT}; "
            "refusing to publish truncated audio"
        )

    residual = base.hktrad.residual_latin_tokens(script)
    if residual:
        raise RuntimeError("residual Latin gate after spelling fallback: " + ", ".join(residual))
    if len(script) < 8:
        raise RuntimeError("story too short")
    return script


# Preserve all of the proven synthesis/runtime code, but replace the text
# collector with the full-article implementation above.
base.script = full_script
_original_synth = base.synth


def verified_synth(tts, ref, story, out_path):
    expected = full_script(story)
    result = _original_synth(tts, ref, story, out_path)
    spoken = "".join(str(unit.get("text") or "") for unit in result.get("semanticUnits") or [])

    # Segmentation may strip boundary whitespace, but it must never drop actual
    # article characters or stop mid-sentence.
    normalize = lambda value: re.sub(r"\s+", "", str(value or ""))
    if normalize(spoken) != normalize(expected):
        raise RuntimeError(
            f"semantic-unit completeness check failed for {story.get('id') or story.get('title')}"
        )

    result["contentCoveragePolicy"] = COVERAGE_POLICY
    result["contentComplete"] = True
    result["inputTextChars"] = len(expected)
    return result


base.synth = verified_synth


if __name__ == "__main__":
    raise SystemExit(base.main())
