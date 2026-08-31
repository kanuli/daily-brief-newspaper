#!/usr/bin/env python3
"""Run canto-nano production with full visible-article TTS coverage.

This wrapper removes silent article/body truncation from the legacy production
module and verifies that semantic-unit segmentation preserves the complete
selected script before a WAV can be published.

Hong Kong mixed-language policy:
- use established Hong Kong Traditional-Chinese names where they genuinely
  exist;
- preserve official English brand, product, organisation and proper names when
  that is normal Hong Kong usage;
- allow natural Cantonese + English code-switching because canto-tts-nano is
  explicitly trained and evaluated for it;
- never invent literal Chinese translations merely to eliminate Latin letters.
"""
from __future__ import annotations

import re

import canto_nano_prod as base
import tts_hktrad_v3 as hkpolicy

# Force the production wrapper to use the HK mixed-language policy even though
# the legacy base module still imports tts_hktrad_v2 internally.
base.hktrad = hkpolicy

COVERAGE_POLICY = "full-visible-article-no-truncation-v1"
ENGLISH_POLICY = "hk-natural-cantonese-english-codeswitch-v4"

# Bump the asset namespace whenever speech normalization semantics change.
# cnf4 forces current articles to be regenerated under the actual production
# HK terminology policy rather than reusing cnf3 recordings.
base.NS = "cnf4"


def localize_mixed_english(text: str) -> str:
    """Apply only established HK localization; preserve valid English names."""
    return base.hktrad.localize(text)


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

    # Every body paragraph visible on the article page belongs in the spoken
    # version as well.
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
        text = localize_mixed_english(raw)
        if text and text[-1] not in "。！？!?":
            text += "。"
        out.append(text)

    script = "".join(out)
    if base.LIMIT > 0 and len(script) > base.LIMIT:
        raise RuntimeError(
            f"article exceeds configured TTS guard: {len(script)}>{base.LIMIT}; "
            "refusing to publish truncated audio"
        )

    # English is deliberately NOT a failure condition. canto-tts-nano keeps
    # English orthography through its HK Cantonese G2P pipeline and is trained
    # for natural English code-switching.
    if len(script) < 8:
        raise RuntimeError("story too short")
    return script


# Preserve the proven synthesis/runtime code while replacing only the text
# collector and adding output completeness verification.
base.script = full_script
_original_synth = base.synth


def verified_synth(tts, ref, story, out_path):
    expected = full_script(story)
    result = _original_synth(tts, ref, story, out_path)
    spoken = "".join(str(unit.get("text") or "") for unit in result.get("semanticUnits") or [])

    normalize = lambda value: re.sub(r"\s+", "", str(value or ""))
    if normalize(spoken) != normalize(expected):
        raise RuntimeError(
            f"semantic-unit completeness check failed for {story.get('id') or story.get('title')}"
        )

    # Defensive regression gate: never reintroduce the old letter-by-letter
    # Chinese-comma fallback which broke one English word into many TTS units.
    for unit in result.get("semanticUnits") or []:
        if re.search(r"(?:欸|比|施|啲|伊|艾夫|芝|艾治|艾|啫|基|艾路|艾姆|艾恩|柯|披|翹|亞|艾斯|剔|優|維|打孖優|艾克斯|歪|些德)、", str(unit.get("text") or "")):
            raise RuntimeError("fragmented English-letter TTS regression detected")

    latin_tokens = base.hktrad.residual_latin_tokens(expected)
    result["contentCoveragePolicy"] = COVERAGE_POLICY
    result["contentComplete"] = True
    result["inputTextChars"] = len(expected)
    result["englishHandlingPolicy"] = ENGLISH_POLICY
    result["languageGate"] = "hk-cantonese-english-codeswitch-allowed"
    result["englishCodeSwitchTokenCount"] = len(latin_tokens)
    result["englishCodeSwitchTokens"] = latin_tokens
    return result


base.synth = verified_synth


if __name__ == "__main__":
    raise SystemExit(base.main())
