#!/usr/bin/env python3
"""Regression test for P0 Rolling Desk self-healing.

Covers the exact production failure from issue #59:
valid last-known-good -> zero-byte canonical -> automatic git-history restore ->
valid/current canonical. It also locks the explicit health-state vocabulary used
by the watchdog so missing, zero-byte, invalid JSON, stale and current cannot be
collapsed into a generic failure.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

import restore_complete_desk_reservoir as reservoir
from validate_desk_integrity import FLOORS, inspect


def run(*args: str, cwd: Path) -> str:
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def complete_desk(cycle: str) -> dict:
    desks = {}
    for slug, floor in FLOORS.items():
        desks[slug] = [
            {
                "id": f"{slug}-{idx}",
                "title": f"{slug} story {idx}",
            }
            for idx in range(floor)
        ]
    return {
        "date": cycle[:10],
        "generatedAt": cycle,
        "mode": "ROLLING_DESK_LATEST",
        "desks": desks,
    }


def assert_state(expected: str, desk: Path, live: Path) -> dict:
    state, detail = inspect(desk, live)
    if state != expected:
        raise AssertionError(f"expected {expected}, got {state}: {detail}")
    return detail


def main() -> int:
    cycle = "2026-09-19T01:00:00+08:00"
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        data = root / "data"
        data.mkdir(parents=True)
        desk = data / "desk-latest.json"
        live = data / "live.json"

        live.write_text(
            json.dumps({"date": cycle[:10], "lastUpdated": cycle}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        desk.write_text(json.dumps(complete_desk(cycle), ensure_ascii=False) + "\n", encoding="utf-8")

        run("git", "init", "-q", cwd=root)
        run("git", "config", "user.name", "Self Heal Test", cwd=root)
        run("git", "config", "user.email", "self-heal@example.invalid", cwd=root)
        run("git", "add", "data/desk-latest.json", "data/live.json", cwd=root)
        run("git", "commit", "-q", "-m", "last known good", cwd=root)

        detail = assert_state("CURRENT", desk, live)
        if detail.get("depthMet") is not True:
            raise AssertionError(detail)

        # Reproduce #59: canonical file exists but is exactly zero bytes.
        desk.write_bytes(b"")
        assert_state("ZERO_BYTE", desk, live)

        old_cwd = Path.cwd()
        old_path = reservoir.DESK_PATH
        old_age = reservoir.MAX_HISTORY_AGE_SECONDS
        try:
            os.chdir(root)
            reservoir.DESK_PATH = Path("data/desk-latest.json")
            reservoir.MAX_HISTORY_AGE_SECONDS = 10 * 365 * 24 * 60 * 60
            reservoir._restore_recent_complete_reservoir()
        finally:
            reservoir.DESK_PATH = old_path
            reservoir.MAX_HISTORY_AGE_SECONDS = old_age
            os.chdir(old_cwd)

        recovered = assert_state("CURRENT", desk, live)
        if recovered.get("generatedAt") != cycle:
            raise AssertionError(recovered)
        if recovered.get("depthMet") is not True:
            raise AssertionError(recovered)

        # Downstream may only be signalled from a fully current, depth-complete state.
        downstream_ready = recovered.get("depthMet") is True
        if not downstream_ready:
            raise AssertionError("recovered current desk did not become downstream-ready")

        desk.write_text("{broken", encoding="utf-8")
        assert_state("INVALID_JSON", desk, live)

        desk.unlink()
        assert_state("MISSING", desk, live)

        desk.write_text(json.dumps(complete_desk("2026-09-19T00:00:00+08:00")) + "\n", encoding="utf-8")
        assert_state("STALE", desk, live)

    print(
        "ROLLING_DESK_SELF_HEAL_TEST_PASS "
        "states=MISSING,ZERO_BYTE,INVALID_JSON,STALE,CURRENT "
        "lastKnownGoodPreserved=true regeneration=current downstreamReady=true"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
