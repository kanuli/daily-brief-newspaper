#!/usr/bin/env python3
"""Technical-unit and speech-number localization used by Cantonese TTS."""
import re

# Unit tokens may be attached directly to digits (for example 2nm), so these
# deliberately use alphabetic rather than alphanumeric boundaries.
UNIT_REPLACEMENTS = [
    ("nm", "納米"),
]

_DIGITS = "零一二三四五六七八九"
_SMALL_UNITS = ("", "十", "百", "千")
_BIG_UNITS = ("", "萬", "億", "兆")
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９．，", "0123456789.,")
# Do not start in the middle of identifiers/decimals/grouped values. This keeps
# codes such as M5.9 and A66 intact unless an explicit newsroom override exists.
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9０-９.,，．])([0-9０-９][0-9０-９,，]*(?:[.．][0-9０-９]+)?)(?![A-Za-z0-9０-９])"
)


def _four_digits_to_chinese(number):
    """Read one 0..9999 group using Cantonese-compatible Chinese numerals."""
    number = int(number)
    if number == 0:
        return ""
    out = []
    zero_pending = False
    for pos in range(3, -1, -1):
        unit_value = 10 ** pos
        digit, number = divmod(number, unit_value)
        if digit:
            if zero_pending and out:
                out.append("零")
            # 10..19 is normally read 十、十一... rather than 一十、一十一.
            if not (pos == 1 and digit == 1 and not out):
                out.append(_DIGITS[digit])
            out.append(_SMALL_UNITS[pos])
            zero_pending = False
        elif out and number:
            zero_pending = True
    return "".join(out)


def _integer_to_chinese(raw, *, year=False):
    raw = str(raw).lstrip("0") or "0"
    # Calendar years are read digit by digit: 2026年 -> 二零二六年. A plain
    # quantity such as 2,026人 must remain 二千零二十六人 instead.
    if year and len(raw) == 4:
        return "".join(_DIGITS[int(char)] for char in raw)
    number = int(raw)
    if number == 0:
        return "零"

    groups = []
    while number:
        groups.append(number % 10000)
        number //= 10000
    if len(groups) > len(_BIG_UNITS):
        # Extremely large identifiers are safer digit-by-digit than inventing
        # unsupported Chinese large-number units.
        return "".join(_DIGITS[int(char)] for char in raw)

    out = []
    zero_between = False
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            if out:
                zero_between = True
            continue
        if out and (zero_between or group < 1000):
            if out[-1] != "零":
                out.append("零")
        out.append(_four_digits_to_chinese(group))
        out.append(_BIG_UNITS[index])
        zero_between = False
    return "".join(out)


def _number_for_speech(match):
    raw = match.group(1).translate(_FULLWIDTH_DIGITS).replace(",", "")
    next_char = match.string[match.end():match.end() + 1]
    is_year = next_char == "年"
    if "." in raw:
        whole, fraction = raw.split(".", 1)
        return f"{_integer_to_chinese(whole, year=False)}點{''.join(_DIGITS[int(char)] for char in fraction)}"
    return _integer_to_chinese(raw, year=is_year)


def normalize_numbers_for_cantonese(text):
    """Normalize numbers before punctuation-based TTS segmentation.

    Thousands separators are formatting, not pauses. Converting the full number
    here guarantees e.g. 2,800億 -> 二千八百億 before the segmenter sees it.
    """
    return _NUMBER_RE.sub(_number_for_speech, str(text or ""))


def localize_units(text):
    out = str(text or "")
    # Resolve attached technical units first so 2nm becomes 2納米, then convert
    # the number. Identifier-like tokens such as 4DX remain untouched.
    for source, target in sorted(UNIT_REPLACEMENTS, key=lambda item: len(item[0]), reverse=True):
        out = re.sub(
            r"(?<![A-Za-z])" + re.escape(source) + r"(?![A-Za-z])",
            target,
            out,
            flags=re.IGNORECASE,
        )
    # This still runs before canto_nano_prod.units() splits punctuation, so a
    # thousands comma can never become an artificial pause.
    return normalize_numbers_for_cantonese(out)
