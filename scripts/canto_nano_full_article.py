#!/usr/bin/env python3
"""Run canto-nano production with full visible-article TTS coverage.

This wrapper removes silent article/body truncation from the legacy production
module and verifies that semantic-unit segmentation preserves the complete
selected script before a WAV can be published.

Mixed-English policy:
- use the shared HK Traditional-Chinese newsroom dictionary first;
- translate high-frequency English phrases that previously reached the fallback;
- spell only the remaining Latin token in one compact Cantonese unit;
- never insert Chinese list commas between letters, because `、` is a TTS
  segmentation boundary and previously exploded one English word into many
  tiny synthesis calls.
"""
from __future__ import annotations

import re

import canto_nano_prod as base

COVERAGE_POLICY = "full-visible-article-no-truncation-v1"
ENGLISH_POLICY = "hk-chinese-first-compact-latin-fallback-v2"

# Bump the asset namespace whenever speech normalization semantics change.
# This makes old cnf1 WAV files ineligible for cache reuse and forces current
# articles to be regenerated under the corrected mixed-English policy.
base.NS = "cnf2"

# Residual phrases observed in current/recent newsroom copy. These sit after
# tts_hktrad_v2, so the larger shared dictionary remains the primary source of
# Hong Kong newsroom names and terminology.
ENGLISH_OVERRIDES = [
    ("Sky Sports", "天空體育"),
    ("Lancaster County", "蘭開斯特縣"),
    ("Ross Fire", "羅斯山火"),
    ("Palo Pinto", "帕洛平托"),
    ("Jack Counties", "傑克縣"),
    ("CDC", "美國疾病控制及預防中心"),
    ("MMR", "麻疹流行性腮腺炎及德國麻疹混合疫苗"),
    ("County", "縣"),
    ("Counties", "各縣"),
    ("Sports", "體育"),
]

LETTER_NAMES = {
    "A": "欸", "B": "比", "C": "施", "D": "啲", "E": "伊", "F": "艾夫",
    "G": "芝", "H": "艾治", "I": "艾", "J": "啫", "K": "基", "L": "艾路",
    "M": "艾姆", "N": "艾恩", "O": "柯", "P": "披", "Q": "翹", "R": "亞",
    "S": "艾斯", "T": "剔", "U": "優", "V": "維", "W": "打孖優",
    "X": "艾克斯", "Y": "歪", "Z": "些德",
}

# Keep punctuation that belongs to the Latin identifier inside one match. The
# replacement itself contains no segmentation punctuation.
LATIN_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z][A-Za-z0-9.+&'’/-]*)(?![A-Za-z0-9])")


def _replace_phrase(text: str, source: str, target: str) -> str:
    return re.sub(
        r"(?<![A-Za-z0-9])" + re.escape(source) + r"(?![A-Za-z0-9])",
        target,
        text,
        flags=re.IGNORECASE,
    )


def localize_mixed_english(text: str) -> str:
    """Return Cantonese-safe text without fragmenting English into TTS units."""
    out = base.hktrad.localize(text)
    for source, target in sorted(ENGLISH_OVERRIDES, key=lambda item: len(item[0]), reverse=True):
        out = _replace_phrase(out, source, target)

    def compact_spell(match: re.Match[str]) -> str:
        token = match.group(1)
        spoken = []
        for ch in token:
            if ch.isalpha():
                spoken.append(LETTER_NAMES[ch.upper()])
            elif ch.isdigit():
                spoken.append("零一二三四五六七八九"[int(ch)])
            # Punctuation inside an identifier is deliberately omitted from the
            # speech fallback rather than becoming a segmentation boundary.
        return "".join(spoken) or token

    if base.hktrad.residual_latin_tokens(out):
        out = LATIN_TOKEN_RE.sub(compact_spell, out)
    return out


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

    residual = base.hktrad.residual_latin_tokens(script)
    if residual:
        raise RuntimeError(
            "residual Latin gate after compact fallback: " + ", ".join(residual)
        )
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

    # Defensive regression gate: a compact English fallback must never create
    # the old one-letter-list segmentation pattern.
    for unit in result.get("semanticUnits") or []:
        if re.search(r"(?:欸|比|施|啲|伊|艾夫|芝|艾治|艾|啫|基|艾路|艾姆|艾恩|柯|披|翹|亞|艾斯|剔|優|維|打孖優|艾克斯|歪|些德)、", str(unit.get("text") or "")):
            raise RuntimeError("fragmented English-letter TTS regression detected")

    result["contentCoveragePolicy"] = COVERAGE_POLICY
    result["contentComplete"] = True
    result["inputTextChars"] = len(expected)
    result["englishHandlingPolicy"] = ENGLISH_POLICY
    return result


base.synth = verified_synth


if __name__ == "__main__":
    raise SystemExit(base.main())
