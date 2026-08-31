#!/usr/bin/env python3
"""Pre-publication audit for Hong Kong Cantonese-English newsroom speech.

The gate mirrors the current Canto Nano source set and is intentionally
conservative:
- official English names that Hong Kong media commonly keeps in English must
  survive speech localization unchanged;
- long-established Hong Kong Chinese names must still localize correctly;
- unknown English is allowed and reported, never auto-rejected or invented as
  a literal Chinese translation;
- known bad literal translations block publication.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import tts_hktrad_v3 as hk

BASE_SOURCE_FILES = (
    Path("data/latest.json"),
    Path("data/desk-latest.json"),
    Path("data/live.json"),
    Path("data/stocks-latest.json"),
)

PRESERVE_CASES = {
    "OpenAI": "OpenAI",
    "ChatGPT": "ChatGPT",
    "Google": "Google",
    "iPhone": "iPhone",
    "Android": "Android",
    "NVIDIA": "NVIDIA",
    "Meta": "Meta",
    "Gemini": "Gemini",
    "Copilot": "Copilot",
    "API": "API",
    "GPU": "GPU",
    "AI": "AI",
}

HK_CHINESE_CASES = {
    "Microsoft": "微軟",
    "Federal Reserve": "美國聯儲局",
    "Manchester United": "曼聯",
    "Reuters": "路透社",
    "Bloomberg": "彭博",
    "HSBC": "滙豐",
}

# Synthetic name that deliberately has no dictionary entry.  It verifies the
# default Hong Kong rule: an unfamiliar official English/proper name stays in
# English instead of being letter-spelled or given an invented Chinese name.
UNKNOWN_ENGLISH_PROBE = "ZXQTestBrand"


def current_source_files() -> list[Path]:
    paths = list(BASE_SOURCE_FILES)
    latest = Path("data/latest.json")
    if latest.exists():
        try:
            date = str(json.loads(latest.read_text(encoding="utf-8")).get("date") or "").strip()
        except Exception:
            date = ""
        if date:
            paths.extend(
                (
                    Path(f"data/topic-more/{date}.json"),
                    Path(f"data/editorial-overrides/{date}.json"),
                )
            )
    return paths


def iter_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)
    elif isinstance(value, str):
        yield value


def _contains_ascii_term(text: str, term: str) -> bool:
    return bool(
        re.search(
            r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])",
            text,
            flags=re.IGNORECASE,
        )
    )


def assert_policy_examples() -> None:
    for source, expected in PRESERVE_CASES.items():
        sample = f"香港科技消息：{source} 今日公布更新。"
        out = hk.localize(sample)
        if expected not in out:
            raise RuntimeError(
                f"HK English preservation regression: {source!r} -> {out!r}"
            )

    unknown_sample = f"香港消息：{UNKNOWN_ENGLISH_PROBE} 今日公布更新。"
    unknown_out = hk.localize(unknown_sample)
    if UNKNOWN_ENGLISH_PROBE not in unknown_out:
        raise RuntimeError(
            f"unknown English must remain official English: "
            f"{UNKNOWN_ENGLISH_PROBE!r} -> {unknown_out!r}"
        )

    for source, expected in HK_CHINESE_CASES.items():
        sample = f"新聞消息：{source} 今日公布更新。"
        out = hk.localize(sample)
        if expected not in out:
            raise RuntimeError(
                f"HK established-name regression: {source!r} -> {out!r}; expected {expected!r}"
            )


def audit_current_copy() -> dict:
    files = 0
    strings = 0
    mixed_strings = 0
    latin_tokens = set()
    checked_paths = []

    for path in current_source_files():
        if not path.exists():
            continue
        files += 1
        checked_paths.append(path.as_posix())
        data = json.loads(path.read_text(encoding="utf-8"))
        for raw in iter_strings(data):
            strings += 1
            localized = hk.localize(raw)

            # Reject the bad literal form only when this string actually
            # contains the corresponding official English name.  This avoids
            # false positives if generic Chinese wording happens to be valid
            # in another editorial context.
            for source_term, bad_translation in hk.FORBIDDEN_LITERAL_TRANSLATIONS.items():
                if _contains_ascii_term(raw, source_term) and bad_translation in localized:
                    raise RuntimeError(
                        f"HK terminology gate rejected {source_term!r} -> "
                        f"{bad_translation!r} in {path}"
                    )

            tokens = hk.residual_latin_tokens(raw)
            if tokens:
                mixed_strings += 1
                latin_tokens.update(tokens)

    return {
        "sourceFilesChecked": files,
        "sourcePathsChecked": checked_paths,
        "stringsChecked": strings,
        "mixedLanguageStrings": mixed_strings,
        "englishCodeSwitchTokens": sorted(latin_tokens, key=str.lower),
    }


def main() -> int:
    assert_policy_examples()
    result = audit_current_copy()
    print("HK_LANGUAGE_PREFLIGHT_PASS")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
