#!/usr/bin/env python3
"""Regression checks for fail-closed atomic newsroom publication."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from atomic_publish import atomic_write_json, atomic_write_text


def main() -> int:
    with tempfile.TemporaryDirectory() as raw_dir:
        root = Path(raw_dir)
        target = root / "desk-latest.json"
        original = {"state": "last-known-good", "desks": {"world": [{"id": "good"}]}}
        target.write_text(json.dumps(original) + "\n", encoding="utf-8")
        original_bytes = target.read_bytes()

        def reject(_raw: str) -> None:
            raise ValueError("simulated producer/validation failure")

        try:
            atomic_write_text(target, "{}\n", validator=reject)
        except ValueError:
            pass
        else:
            raise AssertionError("rejected candidate unexpectedly replaced canonical file")

        if target.read_bytes() != original_bytes:
            raise AssertionError("last-known-good canonical file was not preserved")

        candidate = {"state": "current", "desks": {"world": [{"id": "new"}]}}
        atomic_write_json(target, candidate)
        if json.loads(target.read_text(encoding="utf-8")) != candidate:
            raise AssertionError("valid candidate was not atomically published")

        leftovers = list(root.glob(".desk-latest.json.*.tmp"))
        if leftovers:
            raise AssertionError(f"temporary publication files leaked: {leftovers}")

    print("ATOMIC_PUBLICATION_REGRESSION_PASS last-known-good-preserved=true replacement=valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
