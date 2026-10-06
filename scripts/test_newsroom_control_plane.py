#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "newsroom_control_plane.py"
REGISTRY = ROOT / "config" / "newsroom-robots.json"
NOW = datetime(2026, 10, 6, 8, 55, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat().replace("+00:00", "Z")


def write(path: Path, data):
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def base_files():
    return {
        "staging": {
            "lastSearchAt": NOW_ISO,
            "underfilledDesks": {},
            "queryAudit": {
                "world": {"floorMetThisRun": 1},
                "japan": {"floorMetThisRun": 1},
                "manchester-united": {"floorMetThisRun": 1},
            },
            "desks": {
                "world": [{"publishedAt": NOW_ISO}],
                "japan": [{"publishedAt": NOW_ISO}],
                "manchester-united": [{"publishedAt": NOW_ISO}],
            },
        },
        "prepublish": {},
        "freshness": {
            "desks": {
                "world": {"fresh": True, "dailySynced": True, "newestAgeHours": 1},
                "japan": {"fresh": True, "dailySynced": True, "newestAgeHours": 1},
                "manchester-united": {"fresh": True, "dailySynced": True, "newestAgeHours": 1},
            }
        },
        "editor": {"findings": [], "repairPlan": [], "voiceWorkflowAudit": {"coverageComplete": True}},
        "sentinel": {"checkedAt": NOW_ISO, "persistentFailedPages": []},
        "previous": {},
        "latest": {"date": "2026-10-06"},
        "live": {"lastUpdated": NOW_ISO},
        "desk": {"generatedAt": NOW_ISO},
        "stocks": {"generatedAt": NOW_ISO, "lastCheckedAt": NOW_ISO},
        "tts": {"coverageComplete": True, "pendingArticleCount": 0},
    }


def run_case(
    *,
    mutate=None,
    stock_rc=0,
    publication_rc=0,
    vocab_rc=0,
    trigger_workflow="",
    trigger_conclusion="",
):
    data = base_files()
    if mutate:
        mutate(data)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        paths = {name: write(td / f"{name}.json", value) for name, value in data.items()}
        out = td / "out.json"
        subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--registry",
                str(REGISTRY),
                "--staging",
                str(paths["staging"]),
                "--prepublish",
                str(paths["prepublish"]),
                "--freshness",
                str(paths["freshness"]),
                "--editor-status",
                str(paths["editor"]),
                "--sentinel",
                str(paths["sentinel"]),
                "--previous-assignments",
                str(paths["previous"]),
                "--latest",
                str(paths["latest"]),
                "--live",
                str(paths["live"]),
                "--desk",
                str(paths["desk"]),
                "--stocks",
                str(paths["stocks"]),
                "--tts",
                str(paths["tts"]),
                "--stock-rc",
                str(stock_rc),
                "--publication-rc",
                str(publication_rc),
                "--vocab-rc",
                str(vocab_rc),
                "--trigger-workflow",
                trigger_workflow,
                "--trigger-conclusion",
                trigger_conclusion,
                "--now",
                NOW_ISO,
                "--output",
                str(out),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return json.loads(out.read_text(encoding="utf-8"))


registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
assert registry["schemaVersion"] == 2, registry
ids = [r["id"] for r in registry["robots"]]
workflows = [r["workflow"] for r in registry["robots"]]
assert len(ids) == len(set(ids)), ids
assert len(workflows) == len(set(workflows)), workflows
assert "daily-recovery" in ids, ids
assert registry["controlPlane"]["leafRobotsManualDispatchOnly"] is True

r = run_case()
assert r["assignments"] == [], r
assert r["healthy"] is True, r

def underfill(d):
    d["staging"]["underfilledDesks"] = {"world": {"count": 5, "floor": 24}}
    d["staging"]["queryAudit"]["world"]["floorMetThisRun"] = 0

r = run_case(mutate=underfill)
collector = next(x for x in r["assignments"] if x["robot"] == "collector")
assert collector["mode"] == "deep", r
assert collector["dispatchInputs"] == {"mode": "deep"}, r

def stale_with_candidates(d):
    d["freshness"]["desks"] = {
        "japan": {"fresh": False, "dailySynced": True, "newestAgeHours": 136},
        "manchester-united": {"fresh": False, "dailySynced": True, "newestAgeHours": 30},
    }

r = run_case(mutate=stale_with_candidates)
robots = {x["robot"] for x in r["assignments"]}
assert "general-producer" in robots, r
assert "desk-merge" not in robots, r
assert "collector" not in robots, r

def pending(d):
    stale_with_candidates(d)
    d["prepublish"] = {
        "status": "VERIFIED_DRAFT",
        "publicationType": "LIVE",
        "draftId": "draft-1",
        "createdAt": NOW_ISO,
        "articles": [{"id": "x"}],
    }

r = run_case(mutate=pending)
robots = {x["robot"] for x in r["assignments"]}
assert "live-publisher" in robots, r
assert "general-producer" not in robots, r

r = run_case(
    mutate=stale_with_candidates,
    trigger_workflow="Live Publication Auto Maintenance",
    trigger_conclusion="success",
)
merge = next(x for x in r["assignments"] if x["robot"] == "desk-merge")
assert merge["dispatchable"] is True, r
assert "general-producer" not in {x["robot"] for x in r["assignments"]}, r

def stock_deep(d):
    d["editor"] = {
        "findings": [{"code": "STOCK_RECOVERY_NO_PROGRESS", "severity": "critical", "area": "stock"}],
        "repairPlan": [{"area": "stock-deep", "workflow": "stock-publication-maintenance.yml"}],
        "voiceWorkflowAudit": {"coverageComplete": True},
    }

r = run_case(mutate=stock_deep, stock_rc=1)
stock = next(x for x in r["assignments"] if x["robot"] == "stock")
assert stock["mode"] == "deep", r
assert stock["dispatchInputs"] == {"recovery_mode": "deep"}, r

def previous_stock_normal_no_progress(d):
    d["previous"] = {
        "cycleId": "old",
        "assignments": [{
            "robot": "stock",
            "workflow": "stock-publication-maintenance.yml",
            "mode": "normal",
            "attempt": 1,
            "outcomeBefore": {
                "stockValidatorOk": False,
                "stockGeneratedAt": NOW_ISO,
                "stockLastCheckedAt": NOW_ISO,
            },
        }],
        "execution": [{
            "workflow": "stock-publication-maintenance.yml",
            "dispatched": True,
            "reason": "assigned-by-editor-in-chief",
        }],
    }

r = run_case(mutate=previous_stock_normal_no_progress, stock_rc=1)
stock = next(x for x in r["assignments"] if x["robot"] == "stock")
assert stock["mode"] == "deep", r
assert stock["attempt"] == 2, r
assert stock["status"] == "escalated", r

def previous_stock_deep_stuck(d):
    d["previous"] = {
        "cycleId": "old",
        "assignments": [{
            "robot": "stock",
            "workflow": "stock-publication-maintenance.yml",
            "mode": "deep",
            "attempt": 2,
            "outcomeBefore": {
                "stockValidatorOk": False,
                "stockGeneratedAt": NOW_ISO,
                "stockLastCheckedAt": NOW_ISO,
            },
        }],
        "execution": [{
            "workflow": "stock-publication-maintenance.yml",
            "dispatched": True,
            "reason": "assigned-by-editor-in-chief",
        }],
    }

r = run_case(mutate=previous_stock_deep_stuck, stock_rc=1)
stock = next(x for x in r["assignments"] if x["robot"] == "stock")
assert stock["status"] == "stuck", r
assert stock["dispatchable"] is False, r
assert r["stuckCount"] == 1, r

def producer_failure(d):
    stale_with_candidates(d)

r = run_case(
    mutate=producer_failure,
    trigger_workflow="General News Verified Producer",
    trigger_conclusion="failure",
)
collector = next(x for x in r["assignments"] if x["robot"] == "collector")
assert collector["mode"] == "deep", r
assert collector["faultClass"] == "producer-exhausted", r

print("NEWSROOM_CONTROL_PLANE_V2_TESTS_OK")
