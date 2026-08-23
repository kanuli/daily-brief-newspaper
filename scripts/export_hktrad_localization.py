#!/usr/bin/env python3
import json
from pathlib import Path

import tts_hktrad
import tts_hktrad_v2

OUT = Path("data/hktrad-localization.json")


def main():
    payload = {
        "version": 1,
        "policy": "hk-traditional-chinese-first; taiwan-traditional-fallback",
        "baseReplacements": tts_hktrad.REPLACEMENTS,
        "shortAcronyms": tts_hktrad.SHORT_ACRONYMS,
        "overrides": tts_hktrad_v2.OVERRIDES,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "HKTRAD_LOCALIZATION_EXPORT_OK",
        f"base={len(payload['baseReplacements'])}",
        f"short={len(payload['shortAcronyms'])}",
        f"overrides={len(payload['overrides'])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
