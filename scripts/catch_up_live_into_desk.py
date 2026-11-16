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
from datetime import datetime

from atomic_publish import atomic_write_json
from merge_live_into_desk import live_item_rejection_reason, merge

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LIVE = DATA / "live.json"
DESK = DATA / "desk-latest.json"


def parse_stamp(value: object) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return stamp if stamp.utcoffset() is not None else None
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
    items = snapshot.get("items")
    if not isinstance(items, list):
        return 0, [("snapshot", "items not an array")]
    for item in items:
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
    if desk_at is None or live_at is None:
        raise SystemExit("ROLLING_DESK_CATCHUP_TIMESTAMP_HOLD")
    if desk_at > live_at:
        raise SystemExit("ROLLING_DESK_CATCHUP_SOURCE_ROLLBACK_HOLD")
    if desk_at == live_at:
        print("ROLLING_DESK_CATCHUP_NONE", desk.get("generatedAt"), current.get("lastUpdated"))
        return 0

    shas = [line.strip() for line in git_output("log", "--format=%H", "--", "data/live.json").splitlines() if line.strip()]
    snapshots: dict[datetime, tuple[str, dict]] = {}
    for sha in shas:
        snap = committed_live(sha)
        if not snap:
            print("ROLLING_DESK_CATCHUP_SKIPPED_REJECTED_SNAPSHOT", sha, "invalid or unavailable Live object")
            continue
        stamp = parse_stamp(snap.get("lastUpdated"))
        if stamp is None:
            print("ROLLING_DESK_CATCHUP_SKIPPED_REJECTED_SNAPSHOT", sha, "invalid or missing Live timestamp")
            continue
        if not (desk_at < stamp < live_at):
            continue
        # Multiple commits can carry the same Live timestamp. Keep only the
        # newest commit returned by git log for that timestamp.
        snapshots.setdefault(stamp, (sha, snap))

    replayed = 0
    skipped = 0
    for stamp, (sha, snapshot) in sorted(snapshots.items()):
        publishable, rejected = publishable_story_count(snapshot)
        if not publishable:
            skipped += 1
            print("ROLLING_DESK_CATCHUP_SKIPPED_REJECTED_SNAPSHOT", sha, stamp.isoformat(), rejected)
            continue
        try:
            _, candidate = merge(snapshot, desk)
        except SystemExit as exc:
            # History remains in Git. Keep its exact commit and rejection in the run log.
            skipped += 1
            print("ROLLING_DESK_CATCHUP_SKIPPED_REJECTED_SNAPSHOT", sha, stamp.isoformat(), exc)
            continue
        desk = candidate
        replayed += 1
        print("ROLLING_DESK_CATCHUP_REPLAYED", sha, stamp.isoformat())

    # Validate the newest snapshot even when no historical candidate survives.
    # Persist only the derived reservoir here. The normal merge workflow updates
    # the Live coverage after Daily sync and revalidates both before Git commit.
    _, desk = merge(current, desk)
    atomic_write_json(DESK, desk)
    print(
        "ROLLING_DESK_CATCHUP_PASS",
        f"replayed={replayed}",
        f"skipped={skipped}",
        f"through={current.get('lastUpdated')}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
