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

import json
import re
from pathlib import Path

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

# Voice publication must never derive its expected set from a transiently
# broken newsroom container.  The primary Live publisher can briefly write an
# incomplete desk-latest.json before the existing Editor-in-Chief watchdog
# restores the full Rolling Desk reservoir.  Without this gate a Canto Nano
# worker can reset to that transient main state, collect only a few dozen
# stories and incorrectly publish coverageComplete=true for the tiny set.
DESK_FLOORS = {
    "world": 8,
    "asia": 8,
    "hong-kong": 6,
    "japan": 8,
    "market-economy": 8,
    "ai-tech": 6,
    "manga-anime": 4,
    "manchester-united": 4,
    "football": 10,
}


def _publication_state_is_healthy() -> tuple[bool, str]:
    try:
        live = json.loads(Path("data/live.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return False, f"live-json-unreadable:{type(exc).__name__}"

    coverage = live.get("coverage") or {}
    if coverage.get("status") != "COMPLETE":
        return False, f"coverage={coverage.get('status')}"

    for gate in (
        "publishingGateMet",
        "routingGateMet",
        "copyGateMet",
        "footballGateMet",
        "deskLatestDepthMet",
    ):
        if coverage.get(gate) is not True:
            return False, f"{gate}={coverage.get(gate)}"

    counts = coverage.get("deskLatestStoryCounts") or {}
    for desk, floor in DESK_FLOORS.items():
        try:
            count = int(counts.get(desk, 0))
        except (TypeError, ValueError):
            count = 0
        if count < floor:
            return False, f"{desk}={count}<{floor}"

    try:
        desk_raw = Path("data/desk-latest.json").read_bytes()
        if len(desk_raw) < 1024:
            return False, f"desk-latest-bytes={len(desk_raw)}"
        json.loads(desk_raw.decode("utf-8"))
    except Exception as exc:
        return False, f"desk-latest-unreadable:{type(exc).__name__}"

    return True, "complete-publication-state"


_original_collect = base.collect


def guarded_collect():
    healthy, reason = _publication_state_is_healthy()
    if not healthy:
        raise RuntimeError(
            "CANTO_NANO_DEFER_INCOMPLETE_PUBLICATION_STATE " + reason
        )
    return _original_collect()


# Both shard generation and the publish step call base.collect().  The publish
# step first resets to origin/main, so replacing the base-module global here is
# essential: the expected set is revalidated against the exact main snapshot
# that would otherwise be committed into tts-manifest.json.
base.collect = guarded_collect


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


def _semantic_norm(value):
    return re.sub(r"\s+", "", str(value or ""))


def lossless_units(text):
    """Segment speech without ever dropping adjacent punctuation.

    The legacy segmenter can produce a punctuation-only piece when punctuation
    characters are adjacent (for example ``BanG Dream!、Vanguard``). Its empty
    core was discarded, silently removing the second punctuation mark. Keep
    that mark on the preceding semantic unit and enforce a lossless invariant
    before any expensive synthesis begins.
    """
    sty, factor = base.style(text)
    pieces = []
    start = 0
    for match in re.finditer(r"[。！？!?，、；：]", text):
        pieces.append(text[start : match.end()])
        start = match.end()
    if start < len(text):
        pieces.append(text[start:])

    out = []
    for piece in [value.strip() for value in pieces if value.strip()]:
        mark = piece[-1] if piece[-1] in "。！？!?，、；：" else ""
        core = piece[:-1].strip() if mark else piece
        chunks = base.num_refine(base.split_core(core))

        if not chunks:
            # Adjacent punctuation creates a punctuation-only piece. Preserve
            # it on the preceding spoken unit instead of silently dropping it.
            if mark and out:
                out[-1]["text"] += mark
                pause = (
                    base.COMMA
                    if mark in "，、"
                    else base.SEMI
                    if mark in "；："
                    else base.QUESTION
                    if mark in "？?"
                    else base.SENT
                    if mark in "。！!"
                    else 0.0
                )
                if pause:
                    out[-1]["pause"] = max(out[-1]["pause"], round(pause * factor, 3))
                    out[-1]["reason"] = "punctuation"
            continue

        if mark:
            chunks[-1]["text"] += mark
        pause = (
            base.COMMA
            if mark and mark in "，、"
            else base.SEMI
            if mark and mark in "；："
            else base.QUESTION
            if mark and mark in "？?"
            else base.SENT
            if mark and mark in "。！!"
            else 0.0
        )
        if pause:
            chunks[-1]["pause"] = max(chunks[-1]["pause"], pause)
            chunks[-1]["reason"] = "punctuation"
        for chunk in chunks:
            chunk["pause"] = round(chunk["pause"] * factor, 3)
        out += chunks

    if not out:
        raise RuntimeError("zero semantic units")

    spoken = "".join(str(unit.get("text") or "") for unit in out)
    if _semantic_norm(spoken) != _semantic_norm(text):
        raise RuntimeError("lossy semantic-unit segmentation")
    return out, sty, factor


# Preserve the proven synthesis/runtime code while replacing only the text
# collector and adding output completeness verification. The full-article
# wrapper also uses lossless segmentation so the completeness gate cannot be
# tripped by adjacent punctuation being discarded by the legacy tokenizer.
base.script = full_script
base.units = lossless_units
_original_synth = base.synth


def verified_synth(tts, ref, story, out_path):
    expected = full_script(story)
    result = _original_synth(tts, ref, story, out_path)
    spoken = "".join(str(unit.get("text") or "") for unit in result.get("semanticUnits") or [])

    # This exact script-vs-semantic-units equality is the authoritative
    # regression gate. It catches truncation, dropped English, altered names,
    # or any future text mutation without guessing from ambiguous Chinese
    # characters that can legitimately appear in people/place names.
    if _semantic_norm(spoken) != _semantic_norm(expected):
        raise RuntimeError(
            f"semantic-unit completeness check failed for {story.get('id') or story.get('title')}"
        )

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
