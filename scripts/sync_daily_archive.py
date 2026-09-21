#!/usr/bin/env python3
"""Self-heal the Daily archive from valid dated Daily JSON files.

The dated JSON files are the source of truth. This script never invents a
missing edition. It validates every existing dated Daily, rebuilds
``data/archive.json`` deterministically, and creates an archived HTML wrapper
only when the matching dated JSON actually exists and passes validation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from validate_daily_v3 import validate_file

DEFAULT_TOPICS = [
    "世界", "亞洲", "香港", "日本", "📈 財經 / 全球市場", "AI / 科技",
    "漫畫 / Anime", "Manchester United", "Football",
]
DATE_FILE_RE = re.compile(r"^20\d{2}-\d{2}-\d{2}\.json$")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: root must be object")
    return data


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def headline_for(data: dict[str, Any]) -> str:
    articles = [a for a in data.get("articles", []) if isinstance(a, dict)]
    by_id = {str(a.get("id")): a for a in articles if a.get("id")}
    ordered_ids: list[str] = []
    lead = str(data.get("leadId") or "")
    if lead:
        ordered_ids.append(lead)
    for ident in data.get("topFive") or data.get("topFiveIds") or []:
        ident = str(ident or "")
        if ident and ident not in ordered_ids:
            ordered_ids.append(ident)
    ordered = [by_id[i] for i in ordered_ids if i in by_id]
    ordered.extend(a for a in articles if a not in ordered)
    titles = [str(a.get("title") or "").strip() for a in ordered if str(a.get("title") or "").strip()]
    return "；".join(titles[:3]) or "每日晨報"


def topics_for(data: dict[str, Any]) -> list[str]:
    topics: list[str] = []
    for section in data.get("sections") or []:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or section.get("label") or "").strip()
        if title and title not in topics:
            topics.append(title)
    return topics or list(DEFAULT_TOPICS)


def short_date(date_text: str) -> str:
    return datetime.strptime(date_text, "%Y-%m-%d").strftime("%d %b %Y").upper()


def edition_template(root: Path) -> tuple[str, str | None]:
    editions = root / "editions"
    candidates = sorted(editions.glob("20??-??-??.html"), reverse=True)
    for path in candidates:
        text = path.read_text(encoding="utf-8")
        match = re.search(r'data-edition=["\'](20\d{2}-\d{2}-\d{2})["\']', text)
        if match:
            return text, match.group(1)
    raise RuntimeError("No existing archived-edition HTML template is available")


def render_edition(template: str, template_date: str, date_text: str) -> str:
    # The existing archived wrapper is deliberately reused so navbar, assets,
    # accessibility structure, and JS contracts remain identical. Replace the
    # archived date everywhere, including body data-edition and cache-busters.
    return template.replace(template_date, date_text)


def sync(root: Path) -> dict[str, Any]:
    data_dir = root / "data"
    archive_path = data_dir / "archive.json"
    editions_dir = root / "editions"

    existing_archive: dict[str, Any] = {}
    if archive_path.is_file():
        try:
            existing = load_json(archive_path)
            existing_archive = {
                str(row.get("date")): row
                for row in existing.get("editions", [])
                if isinstance(row, dict) and row.get("date")
            }
        except Exception:
            existing_archive = {}

    valid: list[tuple[str, Path, dict[str, Any]]] = []
    skipped: list[dict[str, str]] = []
    for path in sorted(data_dir.glob("20??-??-??.json")):
        if not DATE_FILE_RE.match(path.name):
            continue
        date_text = path.stem
        try:
            data = load_json(path)
            if data.get("date") != date_text:
                raise ValueError(f"embedded date {data.get('date')} != filename {date_text}")
            if not isinstance(data.get("articles"), list) or not data.get("articles"):
                raise ValueError("no articles")
            validate_file(path, f"archive candidate {path.name}", require_top=True)
            valid.append((date_text, path, data))
        except Exception as exc:
            skipped.append({"date": date_text, "reason": str(exc)})

    if not valid:
        raise RuntimeError("No valid dated Daily editions found; refusing to erase archive")

    template, template_date = edition_template(root)
    assert template_date is not None
    generated_wrappers: list[str] = []
    rows: list[dict[str, Any]] = []

    for date_text, _path, data in sorted(valid, key=lambda row: row[0], reverse=True):
        old = existing_archive.get(date_text) or {}
        row = {
            "date": date_text,
            "shortDate": str(old.get("shortDate") or short_date(date_text)),
            "headline": str(old.get("headline") or headline_for(data)),
            "topics": old.get("topics") if isinstance(old.get("topics"), list) and old.get("topics") else topics_for(data),
            "url": f"editions/{date_text}.html",
        }
        rows.append(row)

        wrapper = editions_dir / f"{date_text}.html"
        if not wrapper.is_file():
            atomic_text(wrapper, render_edition(template, template_date, date_text))
            generated_wrappers.append(date_text)

    archive = {"editions": rows}
    atomic_text(archive_path, json.dumps(archive, ensure_ascii=False, separators=(",", ":")) + "\n")

    valid_dates = [row[0] for row in valid]
    missing_calendar_dates: list[str] = []
    if valid_dates:
        first = datetime.strptime(min(valid_dates), "%Y-%m-%d").date()
        last = datetime.strptime(max(valid_dates), "%Y-%m-%d").date()
        valid_set = set(valid_dates)
        cursor = first
        from datetime import timedelta
        while cursor <= last:
            text = cursor.isoformat()
            if text not in valid_set:
                missing_calendar_dates.append(text)
            cursor += timedelta(days=1)

    return {
        "validEditionCount": len(rows),
        "newestDate": rows[0]["date"],
        "generatedEditionWrappers": generated_wrappers,
        "skippedInvalid": skipped,
        "missingDatedEditions": missing_calendar_dates,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    args = ap.parse_args()
    result = sync(Path(args.root).resolve())
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
