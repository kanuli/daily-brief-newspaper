#!/usr/bin/env python3
"""Generate a teacher-quality daily 10-word Japanese vocabulary file.

The newspaper deliberately selects from the vocabulary game's teacher-audited
CORE set, not from the unrestricted advanced dictionary supplement.  An entry is
eligible only when the exact reading+display key is marked common, directly
classified, non-conflicting, and teacher grade A/B in jlpt_teacher_audit.tsv.

JLPT has no official exhaustive post-2010 word list; levels remain this project's
pedagogical classifications.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

CORE_URL = "https://raw.githubusercontent.com/kanuli/japanese-vocab-game/main/data/vocab_core_verified.js"
AUDIT_URL = "https://raw.githubusercontent.com/kanuli/japanese-vocab-game/main/data/jlpt_teacher_audit.tsv"
SOURCE_REPO_URL = "https://github.com/kanuli/japanese-vocab-game"
LEVELS = ("N1", "N2", "N3", "N4", "N5")
ROOT = Path(__file__).resolve().parents[1]
VOCAB_DIR = ROOT / "data" / "vocab"
KANA_RE = re.compile(r"^[\u3040-\u30ffー・ヽヾゝゞ]+$")
ASCII_RE = re.compile(r"[A-Za-z0-9@:/\\]")
BAD_DISPLAY_RE = re.compile(r"[\[\]［］{}<>＜＞]|https?://|www\.", re.I)

# Regression sentinels: dictionary-valid does not automatically mean suitable as a
# representative daily JLPT teaching headword. These exact forms must never return
# to the normal N1-N5 newspaper teaching pool.
BLOCKED_DAILY_KEYS = {
    ("コム", "COM"),
    ("のこったぶん", "残った分"),
    ("アロハ", "アロハ"),
    ("ビア", "ビア"),
}


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Target date in YYYY-MM-DD; defaults to Hong Kong date.")
    return parser.parse_args()


def target_date(value: str | None) -> str:
    if value:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    return datetime.now(ZoneInfo("Asia/Hong_Kong")).date().isoformat()


def download_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "daily-brief-newspaper-vocab-generator/2.0"},
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.read().decode("utf-8")


def parse_js_array(text: str, label: str):
    marker = ",T="
    marker_at = text.find(marker)
    if marker_at < 0:
        raise RuntimeError(f"Could not locate vocabulary array marker ',T=' in {label}")
    array_at = text.find("[", marker_at + len(marker))
    if array_at < 0:
        raise RuntimeError(f"Could not locate vocabulary array in {label}")
    data, _ = json.JSONDecoder().raw_decode(text[array_at:])
    if not isinstance(data, list):
        raise RuntimeError(f"{label} vocabulary source did not decode to a list")
    return data


def parse_audit(text: str):
    rows = {}
    reader = csv.DictReader(io.StringIO(text), delimiter="\t")
    required = {"reading", "display", "level", "grade", "status", "basis", "common"}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise RuntimeError(f"Teacher audit missing columns: {sorted(missing)}")
    for row in reader:
        reading = str(row.get("reading") or "").strip()
        display = str(row.get("display") or "").strip()
        if reading:
            rows[(reading, display)] = row
    if len(rows) < 32000:
        raise RuntimeError(f"Teacher audit unexpectedly small: {len(rows)} exact keys")
    return rows


def clean_teaching_headword(reading: str, display: str) -> bool:
    if not reading or not KANA_RE.fullmatch(reading):
        return False
    shown = display or reading
    if not shown or len(shown) > 24:
        return False
    if ASCII_RE.search(shown) or BAD_DISPLAY_RE.search(shown):
        return False
    if any(ch.isspace() for ch in shown):
        return False
    if (reading, display) in BLOCKED_DAILY_KEYS or (reading, shown) in BLOCKED_DAILY_KEYS:
        return False
    return True


def normalize_core(entries, audit):
    """Return only high-confidence, common, direct teacher-audited core headwords."""
    rows = []
    seen = set()
    rejected = {"not_exact": 0, "not_common": 0, "not_direct": 0, "grade": 0, "form": 0}

    # vocab_core_verified.js tuples:
    # reading, display, level, meaning, meaningSource, levelSource, entryId,
    # teacherGrade, teacherBasis
    for entry in entries:
        if not isinstance(entry, list) or len(entry) < 4:
            continue
        reading = str(entry[0] or "").strip()
        display = str(entry[1] or "").strip()
        meaning = str(entry[3] or "").strip()
        key = (reading, display)
        meta = audit.get(key)
        if not meta:
            rejected["not_exact"] += 1
            continue
        if str(meta.get("common") or "").strip() != "1":
            rejected["not_common"] += 1
            continue
        status = str(meta.get("status") or "").strip()
        if status != "direct":
            rejected["not_direct"] += 1
            continue
        grade = str(meta.get("grade") or "").strip().upper()
        if grade not in {"A", "B"}:
            rejected["grade"] += 1
            continue
        level = str(meta.get("level") or "").strip().upper()
        if level not in LEVELS or not meaning or not clean_teaching_headword(reading, display):
            rejected["form"] += 1
            continue
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "level": level,  # final teacher-audit level is authoritative
                "reading": reading,
                "kanji": display,
                "meaning": meaning,
                # Core overlay has no POS field. Do not invent one.
                "partOfSpeech": "unclassified",
                "teacherGrade": grade,
                "teacherStatus": status,
                "teacherBasis": str(meta.get("basis") or "").strip(),
                "teacherCommon": True,
                "selectionClass": "teacher-core-common-direct",
            }
        )

    counts = {level: sum(1 for row in rows if row["level"] == level) for level in LEVELS}
    short = {level: count for level, count in counts.items() if count < 2}
    if short:
        raise RuntimeError(f"Teacher-quality core pool underfilled: {short}; counts={counts}; rejected={rejected}")
    print(f"TEACHER_POOL_OK counts={counts} rejected={rejected}")
    return rows


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
        fresh = [row for row in level_rows if (row["reading"], row["kanji"]) not in used]
        # Reuse is allowed only after the fresh high-quality pool is exhausted; never
        # degrade into an unreviewed or uncommon word merely to avoid repetition.
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
            raise RuntimeError(f"Could not select two teacher-quality words for {level}")
        selected.extend(picked)

    if len(selected) != 10:
        raise RuntimeError(f"Expected 10 words, selected {len(selected)}")
    return selected


def validate_selected(words):
    if len(words) != 10:
        raise RuntimeError(f"Expected 10 words, got {len(words)}")
    seen = set()
    for word in words:
        key = (word["reading"], word["kanji"])
        if key in seen:
            raise RuntimeError(f"Duplicate daily vocabulary key: {key}")
        seen.add(key)
        if word.get("teacherGrade") not in {"A", "B"}:
            raise RuntimeError(f"Non A/B teacher grade selected: {key}")
        if word.get("teacherStatus") != "direct" or word.get("teacherCommon") is not True:
            raise RuntimeError(f"Non-common/non-direct word selected: {key}")
        if word.get("selectionClass") != "teacher-core-common-direct":
            raise RuntimeError(f"Unexpected selection class: {key}")
        if not clean_teaching_headword(word["reading"], word["kanji"]):
            raise RuntimeError(f"Unsuitable teaching headword selected: {key}")
    counts = {level: sum(1 for word in words if word["level"] == level) for level in LEVELS}
    if any(counts[level] != 2 for level in LEVELS):
        raise RuntimeError(f"Level validation failed: {counts}")
    return counts


def build_payload(date: str, words):
    return {
        "date": date,
        "sourceRepo": "kanuli/japanese-vocab-game",
        "sourceFile": "data/vocab_core_verified.js + data/jlpt_teacher_audit.tsv",
        "sourceUrl": SOURCE_REPO_URL,
        "selectionPolicy": "teacher-core + exact audit + common + direct + grade A/B; no unrestricted advanced-dictionary random picks",
        "levelNote": "JLPT 分級為本站教師審核後的學習用分類；現行 JLPT 並沒有官方完整逐字詞表。",
        "words": words,
    }


def main():
    args = parse_args()
    date = target_date(args.date)
    core_entries = parse_js_array(download_text(CORE_URL), "vocab_core_verified.js")
    audit = parse_audit(download_text(AUDIT_URL))
    rows = normalize_core(core_entries, audit)
    words = choose_words(rows, date)
    counts = validate_selected(words)
    payload = build_payload(date, words)

    VOCAB_DIR.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    dated = VOCAB_DIR / f"{date}.json"
    latest = VOCAB_DIR / "latest.json"
    dated.write_text(body, encoding="utf-8")
    latest.write_text(body, encoding="utf-8")
    print(f"Wrote {dated.relative_to(ROOT)} and {latest.relative_to(ROOT)}: {counts}")


if __name__ == "__main__":
    main()
