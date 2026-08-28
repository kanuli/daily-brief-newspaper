#!/usr/bin/env python3
"""Fail-safe runner for Page News Sentinel.

The core sentinel normally writes its own status snapshot. If a public JSON
endpoint or an unexpected runtime error prevents that, this wrapper still emits
an explicit attention-required status so the maintenance workflow never fails
silently without evidence.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HKT = timezone(timedelta(hours=8))
OUTPUT_FLAG = "--output"
DEFAULT_OUTPUT = "/tmp/page-news-sentinel-status.json"


def output_path(argv: list[str]) -> Path:
    if OUTPUT_FLAG in argv:
        idx = argv.index(OUTPUT_FLAG)
        if idx + 1 < len(argv):
            return Path(argv[idx + 1])
    return Path(DEFAULT_OUTPUT)


def main() -> int:
    args = sys.argv[1:]
    output = output_path(args)
    cmd = [sys.executable, str(Path(__file__).with_name("page_news_sentinel.py")), *args]
    proc = subprocess.run(cmd, check=False)
    if output.is_file() and output.stat().st_size > 0:
        return proc.returncode

    now = datetime.now(timezone.utc)
    payload = {
        "schemaVersion": 1,
        "role": "Page News Sentinel",
        "checkedAt": now.isoformat(),
        "checkedAtHKT": now.astimezone(HKT).isoformat(),
        "status": "EDITORIAL_ATTENTION_REQUIRED",
        "discoveredPageCount": 0,
        "healthyPageCount": 0,
        "failedPageCount": 1,
        "persistentFailedPages": [],
        "newlyPersistentFailedPages": [],
        "escalationRequired": True,
        "repairWorkflows": ["pages.yml"],
        "pageResults": [],
        "runnerFailure": {
            "exitCode": proc.returncode,
            "message": "Page News Sentinel terminated before producing a status snapshot.",
        },
        "policy": {
            "fabricateNews": False,
            "fakeFreshness": False,
            "failClosedOnMissingEvidence": True,
        },
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
