#!/usr/bin/env python3
"""Generate the daily 10-word Japanese vocabulary file for the newspaper."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE_URL = "https://raw.githubusercontent.com/kanuli/japanese-vocab-game/main/data/advanced_vocab.js"
SOURCE_REPO_URL = "https://github.com/kanuli/japanese-vocab-game"
LEVELS = ("N1", "N2", "N3", "N4", "N5")
ROOT = Path(__file__).resolve().parents[1]
VOCAB_DIR = ROOT / "data" / "vocab"


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date in YYYY-MM-DD; defaults to Hong Kong date.")
    return parser.parse_args()


def target_date(value: str | None) -> str:
    if value:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).date().isoformat()


def download_source() -> str:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "daily-brief-newspaper-vocab-generator/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def parse_source(text: str):
    marker = ",T="
    marker_at = text.find(marker)
    if marker_at < 0:
        raise RuntimeError("Could not locate vocabulary array marker ',T=' in advanced_vocab.js")
    array_at = text.find("[", marker_at + len(marker))
    if array_at < 0:
        raise RuntimeError("Could not locate vocabulary array in advanced_vocab.js")
    data, _ = json.JSONDecoder().raw_decode(text[array_at:])
    if not isinstance(data, list):
        raise RuntimeError("Vocabulary source did not decode to a list")
    return data


def load_used_pairs(target: str):
    used = set()
    if not VOCAB_DIR.exists():
        return used
    for path in VOCAB_DIR.glob("20??-??-??.json"):
        if path.name == f"{target}.json":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for word in payload.get("words", []):
            used.add((str(word.get("reading", "")), str(word.get("kanji", ""))))
    return used


def normalize(entries):
    rows = []
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 5:
            continue
        level, reading, kanji, meaning, pos = (str(x or "").strip() for x in entry[:5])
        if level not in LEVELS or not reading or not meaning:
            continue
        rows.append(
            {
                "level": level,
                "reading": reading,
                "kanji": kanji,
                "meaning": meaning,
                "partOfSpeech": pos,
            }
        )
    return rows


def stable_rank(date: str, word: dict):
    identity = "|".join(
        (date, word["level"], word["reading"], word["kanji"], word["meaning"])
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def choose_words(rows, date: str):
    used = load_used_pairs(date)
    selected = []
    selected_pairs = set()

    for level in LEVELS:
        level_rows = [row for row in rows if row["level"] == level]
        fresh = [
            row
            for row in level_rows
            if (row["reading"], row["kanji"]) not in used
        ]
        pool = fresh if len(fresh) >= 2 else level_rows
        pool = sorted(pool, key=lambda row: stable_rank(date, row))

        picked = []
        for row in pool:
            pair = (row["reading"], row["kanji"])
            if pair in selected_pairs:
                continue
            picked.append(row)
            selected_pairs.add(pair)
            if len(picked) == 2:
                break
        if len(picked) != 2:
            raise RuntimeError(f"Could not select two valid words for {level}")
        selected.extend(picked)

    if len(selected) != 10:
        raise RuntimeError(f"Expected 10 words, selected {len(selected)}")
    return selected


def build_payload(date: str, words):
    return {
        "date": date,
        "sourceRepo": "kanuli/japanese-vocab-game",
        "sourceFile": "data/advanced_vocab.js",
        "sourceUrl": SOURCE_REPO_URL,
        "levelNote": "資料中的部分 JLPT 分級為推定，並非官方 JLPT 詞表。",
        "words": words,
    }


def main():
    args = parse_args()
    date = target_date(args.date)
    rows = normalize(parse_source(download_source()))
    words = choose_words(rows, date)
    payload = build_payload(date, words)

    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    dated = VOCAB_DIR / f"{date}.json"
    latest = VOCAB_DIR / "latest.json"
    dated.write_text(body, encoding="utf-8")
    latest.write_text(body, encoding="utf-8")

    counts = {level: sum(1 for word in words if word["level"] == level) for level in LEVELS}
    if any(counts[level] != 2 for level in LEVELS):
        raise RuntimeError(f"Level validation failed: {counts}")
    print(f"Wrote {dated.relative_to(ROOT)} and {latest.relative_to(ROOT)}: {counts}")


if __name__ == "__main__":
    main()
