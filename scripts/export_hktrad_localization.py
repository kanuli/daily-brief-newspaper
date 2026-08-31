#!/usr/bin/env python3
import json
from pathlib import Path

import hktrad_units
import tts_hktrad
import tts_hktrad_v2
import tts_hktrad_v3

OUT = Path("data/hktrad-localization.json")


def _filtered_pairs(pairs):
    """Keep established HK localizations but never override protected official English names."""
    preserve = {term.casefold() for term in tts_hktrad_v3.PRESERVE_OFFICIAL_ENGLISH}
    forbidden_targets = set(tts_hktrad_v3.FORBIDDEN_LITERAL_TRANSLATIONS.values())
    result = []
    for source, target in pairs:
        if str(source).casefold() in preserve:
            continue
        if target in forbidden_targets:
            continue
        result.append((source, target))
    return result


def main():
    base_replacements = _filtered_pairs(tts_hktrad.REPLACEMENTS)
    overrides = _filtered_pairs(tts_hktrad_v2.OVERRIDES)
    payload = {
        "version": 3,
        "policy": "hk-natural-cantonese-english-codeswitch-v4",
        "preserveOfficialEnglish": list(tts_hktrad_v3.PRESERVE_OFFICIAL_ENGLISH),
        "baseReplacements": base_replacements,
        "shortAcronyms": tts_hktrad.SHORT_ACRONYMS,
        "overrides": overrides,
        "unitReplacements": hktrad_units.UNIT_REPLACEMENTS,
    }

    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    for source_term, bad_translation in tts_hktrad_v3.FORBIDDEN_LITERAL_TRANSLATIONS.items():
        if bad_translation in serialized:
            raise RuntimeError(
                f"display terminology export rejected literal translation: "
                f"{source_term} -> {bad_translation}"
            )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(serialized, encoding="utf-8")
    print(
        "HKTRAD_LOCALIZATION_EXPORT_OK",
        f"policy={payload['policy']}",
        f"preserve={len(payload['preserveOfficialEnglish'])}",
        f"base={len(payload['baseReplacements'])}",
        f"short={len(payload['shortAcronyms'])}",
        f"overrides={len(payload['overrides'])}",
        f"units={len(payload['unitReplacements'])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
