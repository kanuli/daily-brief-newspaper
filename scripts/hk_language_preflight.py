#!/usr/bin/env python3
"""Pre-publication audit for Hong Kong Cantonese-English newsroom speech.

The gate mirrors the current Canto Nano source set and is intentionally
conservative:
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

LETTER_SPEECH_NAMES = (
    "打孖優", "艾克斯", "些德", "艾夫", "艾治", "艾路", "艾姆", "艾恩",
    "艾斯", "欸", "比", "施", "啲", "伊", "芝", "艾", "啫", "基", "柯",
    "披", "翹", "亞", "剔", "優", "維", "歪",
)
_LETTER_ALT = "|".join(re.escape(x) for x in sorted(LETTER_SPEECH_NAMES, key=len, reverse=True))
FRAGMENTED_LETTER_PATTERN = re.compile(
    rf"(?:{_LETTER_ALT})(?:、(?:{_LETTER_ALT})){{1,}}"
)


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

            # Only a sequence of two or more letter-name chunks separated by
            # Chinese list commas is the old broken fallback.  A single normal
            # Chinese word followed by `、` is legitimate newsroom copy.
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
