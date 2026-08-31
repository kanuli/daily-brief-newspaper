#!/usr/bin/env python3
"""Pre-publication audit for Hong Kong Cantonese-English newsroom speech.

The gate is intentionally conservative:
- official English names that Hong Kong media commonly keeps in English must
  survive speech localization unchanged;
- long-established Hong Kong Chinese names must still localize correctly;
- unknown English is allowed and reported, never auto-rejected or invented as
  a literal Chinese translation;
- known bad literal translations and the old fragmented letter fallback block
  publication.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import tts_hktrad_v3 as hk

SOURCE_FILES = (
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

FORBIDDEN_OUTPUT = (
    "開放人工智能公司",
    "人工智能聊天機械人",
)

FRAGMENTED_LETTER_PATTERN = re.compile(
    r"(?:欸|比|施|啲|伊|艾夫|芝|艾治|艾|啫|基|艾路|艾姆|艾恩|柯|披|翹|亞|艾斯|剔|優|維|打孖優|艾克斯|歪|些德)、"
)


def iter_strings(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_strings(child)
    elif isinstance(value, str):
        yield value


def assert_policy_examples() -> None:
    for source, expected in PRESERVE_CASES.items():
        sample = f"香港科技消息：{source} 今日公布更新。"
        out = hk.localize(sample)
        if expected not in out:
            raise RuntimeError(
                f"HK English preservation regression: {source!r} -> {out!r}"
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

    for path in SOURCE_FILES:
        if not path.exists():
            continue
        files += 1
        data = json.loads(path.read_text(encoding="utf-8"))
        for raw in iter_strings(data):
            strings += 1
            localized = hk.localize(raw)

            for bad in FORBIDDEN_OUTPUT:
                if bad in localized:
                    raise RuntimeError(
                        f"HK terminology gate rejected {bad!r} in {path}"
                    )

            if FRAGMENTED_LETTER_PATTERN.search(localized):
                raise RuntimeError(
                    f"fragmented English-letter fallback detected in {path}"
                )

            tokens = hk.residual_latin_tokens(raw)
            if tokens:
                mixed_strings += 1
                latin_tokens.update(tokens)

    return {
        "sourceFilesChecked": files,
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
