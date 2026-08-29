#!/usr/bin/env python3
"""Replay missed committed Live snapshots into the Rolling Desk reservoir.

If a previous hourly merge fails, desk-latest.generatedAt can lag behind the
current committed Live snapshot. This script scans git history for committed
`data/live.json` versions newer than the reservoir timestamp and replays them
oldest-first through the normal merge implementation. It prevents the next
successful hour from silently losing distinct stories published during a
failed merge window.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from datetime import datetime

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

    for stamp, snap in ordered:
        LIVE.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        subprocess.run([sys.executable, str(MERGE)], cwd=ROOT, check=True)
        print("ROLLING_DESK_CATCHUP_REPLAYED", stamp.isoformat(), snap.get("windowLabel"))

    # Ensure the working tree finishes with the current snapshot even if git
    # history contained another commit at the same timestamp.
    LIVE.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    subprocess.run([sys.executable, str(MERGE)], cwd=ROOT, check=True)
    print("ROLLING_DESK_CATCHUP_PASS", f"replayed={len(ordered)}", f"through={current.get('lastUpdated')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
