#!/usr/bin/env python3
"""Replay missed committed Live snapshots into the Rolling Desk reservoir.

If a previous hourly merge fails, desk-latest.generatedAt can lag behind the
current committed Live snapshot. This script scans git history for committed
`data/live.json` versions newer than the reservoir timestamp and replays them
oldest-first through the normal merge implementation. It prevents the next
successful hour from silently losing distinct stories published during a
failed merge window.

Historical snapshots that contain no publishable story are quarantined and
skipped. They must not deadlock all later valid snapshots. The current Live
snapshot is still merged fail-closed at the end, so a presently invalid
publication can never be made healthy merely by skipping it.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from datetime import datetime

from atomic_publish import atomic_write_json
from merge_live_into_desk import live_item_rejection_reason

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIVE = DATA / "live.json"
DESK = DATA / "desk-latest.json"
MERGE = ROOT / "scripts" / "merge_live_into_desk.py"


def parse_stamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8")


def committed_live(sha: str) -> dict | None:
    try:
        raw = git_output("show", f"{sha}:data/live.json")
        value = json.loads(raw)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def publishable_story_count(snapshot: dict) -> tuple[int, list[tuple[str, str]]]:
    publishable = 0
    rejected: list[tuple[str, str]] = []
    for item in snapshot.get("items", []):
        if not isinstance(item, dict):
            rejected.append(("unknown", "not an object"))
            continue
        reason = live_item_rejection_reason(item)
        if reason:
            rejected.append((str(item.get("id") or "unknown"), reason))
        else:
            publishable += 1
    return publishable, rejected


def main() -> int:
    desk = json.loads(DESK.read_text(encoding="utf-8"))
    current = json.loads(LIVE.read_text(encoding="utf-8"))
    desk_at = parse_stamp(desk.get("generatedAt"))
    live_at = parse_stamp(current.get("lastUpdated"))
    if desk_at is None or live_at is None or desk_at >= live_at:
        print("ROLLING_DESK_CATCHUP_NONE", desk.get("generatedAt"), current.get("lastUpdated"))
        return 0

    shas = [line.strip() for line in git_output("log", "--format=%H", "--", "data/live.json").splitlines() if line.strip()]
    snapshots: dict[str, tuple[datetime, dict]] = {}
    for sha in shas:
        snap = committed_live(sha)
        if not snap:
            continue
        stamp = parse_stamp(snap.get("lastUpdated"))
        if stamp is None or not (desk_at < stamp <= live_at):
            continue
        # Multiple commits can carry the same Live timestamp. Keep only the
        # newest commit returned by git log for that timestamp.
        snapshots.setdefault(stamp.isoformat(), (stamp, snap))

    ordered = sorted(snapshots.values(), key=lambda pair: pair[0])
    if not ordered:
        print("ROLLING_DESK_CATCHUP_NO_SNAPSHOTS", desk.get("generatedAt"), current.get("lastUpdated"))
        return 0

    replayed = 0
    skipped = 0
    try:
        for stamp, snap in ordered:
            publishable, rejected = publishable_story_count(snap)
            raw_items = snap.get("items", [])
            if not isinstance(raw_items, list) or publishable == 0:
                skipped += 1
                print(
                    "ROLLING_DESK_CATCHUP_SKIPPED_REJECTED_SNAPSHOT",
                    stamp.isoformat(),
                    snap.get("windowLabel"),
                    f"rejected={rejected}",
                )
                continue

            atomic_write_json(LIVE, snap)
            subprocess.run([sys.executable, str(MERGE)], cwd=ROOT, check=True)
            replayed += 1
            print("ROLLING_DESK_CATCHUP_REPLAYED", stamp.isoformat(), snap.get("windowLabel"))
    finally:
        # A replay failure must never leave the working tree pointing at a
        # historical Live snapshot. Always restore the committed current state.
        atomic_write_json(LIVE, current)

    # Current publication stays fail-closed. Historical poison pills may be
    # skipped, but the latest Live must itself pass the normal merge gate.
    subprocess.run([sys.executable, str(MERGE)], cwd=ROOT, check=True)
    print(
        "ROLLING_DESK_CATCHUP_PASS",
        f"replayed={replayed}",
        f"skipped={skipped}",
        f"through={current.get('lastUpdated')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
