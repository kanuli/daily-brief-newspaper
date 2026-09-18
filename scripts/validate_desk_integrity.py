#!/usr/bin/env python3
"""Fail-closed health/integrity gate for the canonical Rolling Desk.

The state label deliberately distinguishes the production failure modes needed
by the newsroom watchdog: MISSING, ZERO_BYTE, INVALID_JSON, STALE and CURRENT.
Depth failure is reported separately and is never publishable.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK_PATH = ROOT / "data" / "desk-latest.json"
LIVE_PATH = ROOT / "data" / "live.json"
FLOORS = {
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


def _load_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("root is not an object")
    return value


def _counts(desk: dict) -> dict[str, int]:
    desks = desk.get("desks")
    if not isinstance(desks, dict):
        return {slug: 0 for slug in FLOORS}
    return {
        slug: len([story for story in (desks.get(slug) or []) if isinstance(story, dict)])
        for slug in FLOORS
    }


def inspect(desk_path: Path = DESK_PATH, live_path: Path = LIVE_PATH) -> tuple[str, dict]:
    if not desk_path.exists():
        return "MISSING", {"bytes": 0}
    size = desk_path.stat().st_size
    if size == 0:
        return "ZERO_BYTE", {"bytes": 0}
    try:
        desk = _load_object(desk_path)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        return "INVALID_JSON", {"bytes": size, "error": str(exc)}

    try:
        live = _load_object(live_path)
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        return "INVALID_JSON", {"bytes": size, "error": f"live: {exc}"}

    counts = _counts(desk)
    desk_at = str(desk.get("generatedAt") or "")
    live_at = str(live.get("lastUpdated") or "")
    detail = {
        "bytes": size,
        "generatedAt": desk_at,
        "liveLastUpdated": live_at,
        "counts": counts,
        "depthMet": all(counts[slug] >= floor for slug, floor in FLOORS.items()),
    }
    if not desk_at or not live_at or desk_at != live_at:
        return "STALE", detail
    return "CURRENT", detail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="allow a complete stale reservoir before automatic Live catch-up",
    )
    args = parser.parse_args()

    state, detail = inspect()
    print(
        "ROLLING_DESK_HEALTH",
        f"state={state}",
        f"bytes={detail.get('bytes', 0)}",
        f"generatedAt={detail.get('generatedAt', '')}",
        f"liveLastUpdated={detail.get('liveLastUpdated', '')}",
        f"depthMet={detail.get('depthMet', False)}",
        f"counts={detail.get('counts', {})}",
    )
    allowed_states = {"CURRENT", "STALE"} if args.allow_stale else {"CURRENT"}
    if state not in allowed_states:
        raise SystemExit(f"Rolling Desk is not publishable: state={state} detail={detail}")
    if detail.get("depthMet") is not True:
        raise SystemExit(f"Rolling Desk is below hard desk floors: {detail.get('counts')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
