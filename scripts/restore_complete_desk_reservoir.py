#!/usr/bin/env python3
"""Restore the most recent complete Rolling Desk after catastrophic truncation.

This is a fail-closed guard for the canonical Rolling Desk merge workflow. It
only activates when several desks have simultaneously fallen below their hard
minimums, which indicates destructive overwrite rather than normal retention.
The guard searches recent git history for the newest desk snapshot that met all
hard depth floors, restores that reservoir, and then lets the existing Daily,
recovery, routing, freshness and Live merge steps revalidate it.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

DESK_PATH = Path("data/desk-latest.json")
HARD_FLOORS = {
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
# Recovery is for a fresh reservoir accident, never an excuse to revive an old
# newsroom. A 24h ceiling comfortably spans the previous verified hourly state.
MAX_HISTORY_AGE_SECONDS = 24 * 60 * 60
# One desk slipping below depth can be an ordinary freshness problem. Multiple
# simultaneous failures indicate a destructive replacement of the reservoir.
CATASTROPHIC_MISSING_DESKS = 4


def _run(*args: str) -> str:
    return subprocess.run(
        args,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def _load(raw: str) -> dict:
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("desk root is not an object")
    return value


def _counts(data: dict) -> dict[str, int]:
    desks = data.get("desks") or {}
    counts: dict[str, int] = {}
    for slug in HARD_FLOORS:
        stories = desks.get(slug) or []
        ids = {
            str(story.get("id") or "").strip()
            for story in stories
            if isinstance(story, dict) and str(story.get("id") or "").strip()
        }
        counts[slug] = len(ids)
    return counts


def _meets_all_floors(counts: dict[str, int]) -> bool:
    return all(counts.get(slug, 0) >= floor for slug, floor in HARD_FLOORS.items())


def _missing_desks(counts: dict[str, int]) -> list[str]:
    return [slug for slug, floor in HARD_FLOORS.items() if counts.get(slug, 0) < floor]


def _restore_recent_complete_reservoir() -> None:
    current_raw = DESK_PATH.read_text(encoding="utf-8") if DESK_PATH.exists() else ""
    try:
        current = _load(current_raw)
        current_counts = _counts(current)
        missing = _missing_desks(current_counts)
    except (json.JSONDecodeError, ValueError):
        # Empty, truncated, malformed, or non-object canonical content is itself
        # catastrophic. Treat every required desk as missing so recovery can
        # search git history instead of crashing before the guard runs.
        current_counts = {slug: 0 for slug in HARD_FLOORS}
        missing = list(HARD_FLOORS)
        print(
            "ROLLING_DESK_RESERVOIR_INVALID_CANONICAL "
            f"bytes={len(current_raw.encode('utf-8'))} counts={current_counts}"
        )

    if len(missing) < CATASTROPHIC_MISSING_DESKS:
        print(
            "ROLLING_DESK_RESERVOIR_GUARD_NOOP "
            f"missing={missing} counts={current_counts}"
        )
        return

    print(
        "ROLLING_DESK_RESERVOIR_TRUNCATION_DETECTED "
        f"missing={missing} counts={current_counts}"
    )

    commits = _run("git", "log", "--format=%H", "--", str(DESK_PATH)).splitlines()
    now = int(time.time())
    for sha in commits:
        sha = sha.strip()
        if not sha:
            continue
        try:
            committed_at = int(_run("git", "show", "-s", "--format=%ct", sha).strip())
        except (ValueError, subprocess.CalledProcessError):
            continue
        if committed_at > now + 300 or now - committed_at > MAX_HISTORY_AGE_SECONDS:
            continue
        try:
            candidate_raw = _run("git", "show", f"{sha}:{DESK_PATH.as_posix()}")
            candidate = _load(candidate_raw)
        except (json.JSONDecodeError, ValueError, subprocess.CalledProcessError):
            continue
        candidate_counts = _counts(candidate)
        if not _meets_all_floors(candidate_counts):
            continue

        DESK_PATH.write_text(candidate_raw.rstrip("\n") + "\n", encoding="utf-8")
        print(
            "ROLLING_DESK_RESERVOIR_RESTORED "
            f"commit={sha} counts={candidate_counts}"
        )
        return

    raise SystemExit(
        "ROLLING_DESK_RESERVOIR_RECOVERY_FAILED: catastrophic truncation found "
        "but no <=24h git snapshot satisfies every hard desk floor"
    )


if __name__ == "__main__":
    _restore_recent_complete_reservoir()
