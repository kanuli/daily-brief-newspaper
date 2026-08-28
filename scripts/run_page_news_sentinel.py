#!/usr/bin/env python3
"""Fail-safe runner for Page News Sentinel.

The core sentinel normally writes its own status snapshot. If a public JSON
endpoint or an unexpected runtime error prevents that, this wrapper still emits
an explicit attention-required status so the maintenance workflow never fails
silently without evidence.

Some public pages expose presentation-level subsection slugs which intentionally
roll up to one canonical newsroom desk. The runner normalizes those aliases
after the core audit so presentation taxonomy is not mistaken for a missing
newsroom collector.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HKT = timezone(timedelta(hours=8))
OUTPUT_FLAG = "--output"
DEFAULT_OUTPUT = "/tmp/page-news-sentinel-status.json"
VIRTUAL_TOPIC_PARENT = {
    "science-new-tech": "ai-tech",
    "cybersecurity": "ai-tech",
    "software-apps": "ai-tech",
}


def output_path(argv: list[str]) -> Path:
    if OUTPUT_FLAG in argv:
        idx = argv.index(OUTPUT_FLAG)
        if idx + 1 < len(argv):
            return Path(argv[idx + 1])
    return Path(DEFAULT_OUTPUT)


def normalize_virtual_topics(data: dict[str, Any]) -> dict[str, Any]:
    """Treat presentation-only topic aliases as children of a fresh canonical desk.

    This does not create freshness. An alias is accepted only when its canonical
    parent desk exists in the same page result and is already proven fresh by the
    core sentinel.
    """
    changed = False
    for row in data.get("pageResults") or []:
        if not isinstance(row, dict) or row.get("kind") != "topic":
            continue
        reasons = list(row.get("reasons") or [])
        detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
        accepted: list[dict[str, str]] = []
        kept: list[str] = []
        for reason in reasons:
            prefix = "unknown topic slug: "
            if not str(reason).startswith(prefix):
                kept.append(reason)
                continue
            slug = str(reason)[len(prefix):].strip()
            parent = VIRTUAL_TOPIC_PARENT.get(slug)
            parent_detail = detail.get(parent) if parent else None
            if parent and isinstance(parent_detail, dict) and parent_detail.get("fresh"):
                accepted.append({"slug": slug, "canonicalDesk": parent})
                detail[slug] = {
                    "fresh": True,
                    "virtualTopic": True,
                    "canonicalDesk": parent,
                    "reason": "presentation-subsection-covered-by-canonical-desk",
                }
                changed = True
            else:
                kept.append(reason)
        if accepted:
            row["virtualTopicAliases"] = accepted
            row["reasons"] = kept
            row["ok"] = not kept

    if not changed:
        return data

    failed = [r for r in data.get("pageResults") or [] if isinstance(r, dict) and not r.get("ok")]
    data["failedPageCount"] = len(failed)
    data["healthyPageCount"] = max(0, int(data.get("discoveredPageCount") or 0) - len(failed))
    failed_pages = {str(r.get("page") or "") for r in failed}
    data["persistentFailedPages"] = [
        page for page in (data.get("persistentFailedPages") or []) if str(page) in failed_pages
    ]
    if not failed:
        data["repairWorkflows"] = []
        data["persistentFailedPages"] = []
        data["status"] = "HEALTHY"
        data.pop("escalationRequired", None)
    data.setdefault("policy", {})["virtualTopicAliasesRequireFreshCanonicalDesk"] = True
    return data


def main() -> int:
    args = sys.argv[1:]
    output = output_path(args)
    cmd = [sys.executable, str(Path(__file__).with_name("page_news_sentinel.py")), *args]
    proc = subprocess.run(cmd, check=False)
    if output.is_file() and output.stat().st_size > 0:
        try:
            data = json.loads(output.read_text(encoding="utf-8"))
            data = normalize_virtual_topics(data)
            output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(data, ensure_ascii=False))
            return 2 if data.get("status") == "EDITORIAL_ATTENTION_REQUIRED" else 0
        except Exception as exc:
            proc = subprocess.CompletedProcess(cmd, 2)
            normalization_error = str(exc)
        else:
            normalization_error = None
    else:
        normalization_error = None

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
            "message": "Page News Sentinel terminated before producing a usable status snapshot.",
            "normalizationError": normalization_error,
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
