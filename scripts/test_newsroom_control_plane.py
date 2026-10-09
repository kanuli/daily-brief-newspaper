#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
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
        "producer_capacity": {},
        "freshness": {
            "desks": {
                "world": {"fresh": True, "dailySynced": True, "newestAgeHours": 1},
                "japan": {"fresh": True, "dailySynced": True, "newestAgeHours": 1},
                "manchester-united": {"fresh": True, "dailySynced": True, "newestAgeHours": 1},
            }
        },
        "editor": {"findings": [], "repairPlan": [], "voiceWorkflowAudit": {"coverageComplete": True}},
        "sentinel": {"checkedAt": NOW_ISO, "persistentFailedPages": []},
        "pages_status": {"checkedAt": NOW_ISO, "match": True},
        "pages_deployment": [],
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
                "--producer-capacity",
                str(paths["producer_capacity"]),
                "--freshness",
                str(paths["freshness"]),
                "--editor-status",
                str(paths["editor"]),
                "--sentinel",
                str(paths["sentinel"]),
                "--pages-status",
                str(paths["pages_status"]),
                "--pages-deployment",
                str(paths["pages_deployment"]),
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

def collector_duty_due(d):
    due=(NOW - timedelta(minutes=13)).isoformat().replace("+00:00", "Z")
    d["staging"]["lastSearchAt"] = due

r = run_case(mutate=collector_duty_due)
collector = next(x for x in r["assignments"] if x["robot"] == "collector")
assert collector["faultClass"] == "collection-duty", r
assert collector["mode"] == "normal", r

def stock_duty_due(d):
    due=(NOW - timedelta(minutes=55)).isoformat().replace("+00:00", "Z")
    d["stocks"]["generatedAt"] = due
    d["stocks"]["lastCheckedAt"] = due

r = run_case(mutate=stock_duty_due)
stock = next(x for x in r["assignments"] if x["robot"] == "stock")
assert stock["faultClass"] == "stock-duty", r
assert stock["mode"] == "normal", r

def underfill(d):
    d["staging"]["underfilledDesks"] = {"world": {"count": 5, "floor": 24}}
    d["staging"]["queryAudit"]["world"]["floorMetThisRun"] = 0

r = run_case(mutate=underfill)
collector = next(x for x in r["assignments"] if x["robot"] == "collector")
assert collector["mode"] == "deep", r
assert collector["dispatchInputs"] == {"mode": "deep"}, r


def stale_and_underfill(d):
    due=(NOW - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    d["staging"]["lastSearchAt"] = due
    d["staging"]["underfilledDesks"] = {"world": {"count": 5, "floor": 24}}
    d["staging"]["queryAudit"]["world"]["floorMetThisRun"] = 0

r = run_case(mutate=stale_and_underfill)
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


def consumed_pending(d):
    pending(d)
    d["live"] = {
        "lastUpdated": NOW_ISO,
        "coverage": {"verifiedDraftId": "draft-1"},
    }

r = run_case(mutate=consumed_pending)
robots = {x["robot"] for x in r["assignments"]}
assert "live-publisher" not in robots, r
assert "general-producer" in robots, r

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
        "checkedAt": NOW_ISO,
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
assert stock["mode"] == "normal", r
assert stock["attempt"] == 1, r
assert stock["previousOutcome"]["evaluation"] == "deferred-in-flight", r

r = run_case(
    mutate=previous_stock_normal_no_progress,
    stock_rc=1,
    trigger_workflow="Stock News Hourly Maintenance",
    trigger_conclusion="success",
)
stock = next(x for x in r["assignments"] if x["robot"] == "stock")
assert stock["mode"] == "deep", r
assert stock["attempt"] == 2, r
assert stock["status"] == "escalated", r

def previous_stock_deep_stuck(d):
    d["previous"] = {
        "cycleId": "old",
        "checkedAt": NOW_ISO,
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

r = run_case(
    mutate=previous_stock_deep_stuck,
    stock_rc=1,
    trigger_workflow="Stock News Hourly Maintenance",
    trigger_conclusion="failure",
)
stock = next(x for x in r["assignments"] if x["robot"] == "stock")
assert stock["status"] == "stuck", r
assert stock["dispatchable"] is False, r
assert r["stuckCount"] == 1, r

def producer_capacity_exhausted(d):
    stale_with_candidates(d)
    d["producer_capacity"] = {
        "status": "QUOTA_EXHAUSTED",
        "checkedAt": NOW_ISO,
        "blockedUntil": (NOW + timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
        "recoveryOwner": "automation:Newsroom Publisher",
    }

r = run_case(mutate=producer_capacity_exhausted)
producer = next(x for x in r["assignments"] if x["robot"] == "general-producer")
assert producer["faultClass"] == "producer-capacity-exhausted", r
assert producer["status"] == "external-failover", r
assert producer["dispatchable"] is False, r
assert producer["blockedBy"] == ["automation:Newsroom Publisher"], r
assert producer["requiresExternalPublisher"] is True, r
assert r["evidenceSnapshot"]["producerCapacityBlocked"] is True, r
assert r["evidenceSnapshot"]["externalPublisherSlotCurrent"] is True, r
assert r["externalPublisherNoProgress"] is False, r

def producer_capacity_expired_but_still_exhausted(d):
    producer_capacity_exhausted(d)
    d["producer_capacity"]["blockedUntil"] = (NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

r = run_case(mutate=producer_capacity_expired_but_still_exhausted)
producer = next(x for x in r["assignments"] if x["robot"] == "general-producer")
assert r["evidenceSnapshot"]["producerCapacityStatus"] == "QUOTA_EXHAUSTED", r
assert r["evidenceSnapshot"]["producerCapacityBlocked"] is True, r
assert producer["faultClass"] == "producer-capacity-exhausted", r
assert producer["status"] == "external-failover", r
assert producer["dispatchable"] is False, r

def producer_local_fallback_failed_stays_blocked(d):
    stale_with_candidates(d)
    d["producer_capacity"] = {
        "status": "LOCAL_FALLBACK_FAILED",
        "checkedAt": NOW_ISO,
        "blockedUntil": None,
        "recoveryOwner": "workflow:general-news-producer.yml",
        "localFallbackModel": "qwen2.5:1.5b",
    }

r = run_case(mutate=producer_local_fallback_failed_stays_blocked)
producer = next(x for x in r["assignments"] if x["robot"] == "general-producer")
assert r["evidenceSnapshot"]["producerCapacityStatus"] == "LOCAL_FALLBACK_FAILED", r
assert r["evidenceSnapshot"]["producerCapacityBlocked"] is True, r
assert producer["faultClass"] == "producer-capacity-exhausted", r
assert producer["dispatchable"] is False, r

def producer_capacity_external_slot_missed(d):
    producer_capacity_exhausted(d)
    stale=(NOW - timedelta(hours=2)).isoformat().replace("+00:00", "Z")
    d["live"] = {"lastUpdated": stale}
    d["desk"] = {"generatedAt": stale}

r = run_case(mutate=producer_capacity_external_slot_missed)
producer = next(x for x in r["assignments"] if x["robot"] == "general-producer")
assert producer["faultClass"] == "external-publisher-no-progress", r
assert producer["status"] == "external-failover-stuck", r
assert producer["dispatchable"] is False, r
assert producer["requiresEditorReplan"] is True, r
assert r["externalPublisherNoProgress"] is True, r
assert r["stuckCount"] >= 1, r
assert r["evidenceSnapshot"]["externalPublisherSlotCurrent"] is False, r

r = run_case(
    mutate=producer_capacity_exhausted,
    trigger_workflow="General News Verified Producer",
    trigger_conclusion="success",
)
assert not any(
    x["robot"] == "collector" and x["faultClass"] == "producer-exhausted"
    for x in r["assignments"]
), r


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



def stock_and_public_fault(d):
    stock_deep(d)
    d["sentinel"] = {
        "checkedAt": NOW_ISO,
        "persistentFailedPages": ["live.html", "stocks.html"],
    }

r = run_case(mutate=stock_and_public_fault, stock_rc=1)
pages = next(x for x in r["assignments"] if x["robot"] == "pages")
stock = next(x for x in r["assignments"] if x["robot"] == "stock")
assert stock["dispatchable"] is True, r
assert pages["dispatchable"] is True, r
assert "stock" not in pages.get("blockedBy", []), r

def live_publication_failure(d):
    d["editor"]["currentDay"] = {"dailyCurrent": True}
    d["editor"]["validatorAudit"] = [{"name": "daily-v3", "ok": True}]
    d["editor"]["findings"] = [{"code": "LIVE_STALE", "area": "live", "severity": "critical"}]

r = run_case(mutate=live_publication_failure, publication_rc=1)
assert "daily-recovery" not in {x["robot"] for x in r["assignments"]}, r
assert "general-producer" in {x["robot"] for x in r["assignments"]}, r
assert r["healthy"] is False, r

r = run_case(publication_rc=1)
assert r["assignments"] == [], r
assert r["healthy"] is False, r  # Unknown validator failure must not become GREEN.

def daily_date_failed(d):
    d["latest"]["date"] = "2026-10-05"

r = run_case(mutate=daily_date_failed, publication_rc=1)
assert "daily-recovery" in {x["robot"] for x in r["assignments"]}, r

def daily_structure_failed(d):
    d["editor"]["validatorAudit"] = [{"name": "daily-v3", "ok": False}]

r = run_case(mutate=daily_structure_failed, publication_rc=1)
assert "daily-recovery" in {x["robot"] for x in r["assignments"]}, r

def editorial_page_gap(d):
    d["sentinel"] = {
        "checkedAt": NOW_ISO,
        "persistentFailedPages": ["world.html"],
        "repairWorkflows": ["rolling-news-search.yml", "merge-live-into-desk.yml"],
        "pageResults": [{"page": "world.html", "kind": "topic", "httpStatus": 200, "ok": False}],
    }

r = run_case(mutate=editorial_page_gap)
assert "pages" not in {x["robot"] for x in r["assignments"]}, r
assert r["healthy"] is False, r  # Correct routing does not erase editorial failure.

def public_http_failed(d):
    d["sentinel"] = {
        "checkedAt": NOW_ISO,
        "persistentFailedPages": ["index.html"],
        "repairWorkflows": ["pages.yml"],
        "pageResults": [{"page": "index.html", "kind": "daily", "httpStatus": 500, "ok": False}],
    }

r = run_case(mutate=public_http_failed)
assert "pages" in {x["robot"] for x in r["assignments"]}, r
assert "daily-recovery" not in {x["robot"] for x in r["assignments"]}, r

def stale_probe_only(d):
    d["pages_status"]["checkedAt"] = (NOW - timedelta(hours=5)).isoformat().replace("+00:00", "Z")
    d["editor"]["findings"] = [
        {"code": "PUBLIC_PROBE_STALE", "area": "pages", "severity": "critical"},
        {"code": "PERSISTENT_PUBLIC_PROBE_STALE", "area": "pages", "severity": "critical"},
    ]

r = run_case(mutate=stale_probe_only)
assert {x["robot"] for x in r["assignments"]} == {"public-probe"}, r
assert "pages" not in {x["robot"] for x in r["assignments"]}, r
assert r["healthy"] is False, r

def actual_propagation_fault(d):
    d["editor"]["findings"] = [{"code": "PUBLIC_LIVE_NOT_PROPAGATED", "area": "pages", "severity": "critical"}]

r = run_case(mutate=actual_propagation_fault)
assert "pages" in {x["robot"] for x in r["assignments"]}, r

from newsroom_control_plane import daily_recovery_required
handover = datetime(2026, 10, 6, 0, 14, tzinfo=timezone.utc)
assert not daily_recovery_required({"date": "2026-10-05"}, {}, handover)
assert not daily_recovery_required(
    {"date": "2026-10-05"},
    {"status": "HEALTHY", "currentDay": {"dailyCurrent": False}},
    handover,
)
assert daily_recovery_required({"date": "2026-10-05"}, {}, handover + timedelta(minutes=1))

def probe_row(result):
    return next(x for x in result["assignments"] if x["robot"] == "public-probe")


# Missing, malformed and changing future clocks remain one stable invalid fault.
for bad_clock in (None, "nonsense", "2026-10-07T08:55:00Z", "2026-10-08T09:55:00Z"):
    def invalid_probe(d, value=bad_clock):
        d["pages_status"] = {"checkedAt": value, "match": True}
    r = run_case(mutate=invalid_probe)
    row = probe_row(r)
    assert row["probeBudgetKey"] == "invalid-public-probe", r
    assert row["dispatchable"] is True, r
    assert {x["robot"] for x in r["assignments"]} == {"public-probe"}, r
    assert r["healthy"] is False, r

stale_stamp = (NOW - timedelta(hours=5)).isoformat().replace("+00:00", "Z")
first = run_case(mutate=lambda d: d["pages_status"].update(checkedAt=stale_stamp))
first_row = probe_row(first)
assert first_row["dispatchable"] is True, first
assert first["publicProbeRecovery"]["maxDispatches"] == 1, first

def after_probe_dispatch(d):
    d["pages_status"]["checkedAt"] = stale_stamp
    d["previous"] = dict(first)
    d["previous"]["execution"] = [{
        "assignmentId": first_row["assignmentId"], "workflow": "pages-probe.yml",
        "dispatched": True, "reason": "assigned-by-editor-in-chief",
    }]

second = run_case(mutate=after_probe_dispatch)
assert probe_row(second)["dispatchable"] is False, second
assert probe_row(second)["status"] == "observation-in-flight", second
assert second["publicProbeRecovery"]["dispatchesUsed"] == 1, second
assert second["healthy"] is False, second

# Completion is not observation/publication, even a reported success.
completed = run_case(mutate=after_probe_dispatch,
    trigger_workflow="Verify Public Pages Publication Snapshot", trigger_conclusion="success")
assert probe_row(completed)["status"] == "stuck", completed
assert completed["stuckCount"] == 1, completed
assert completed["healthy"] is False, completed

def false_execution_after_hold(d):
    d["pages_status"]["checkedAt"] = stale_stamp
    d["previous"] = dict(completed)
    d["previous"]["execution"] = [{
        "assignmentId": probe_row(completed)["assignmentId"], "workflow": "pages-probe.yml",
        "dispatched": False, "reason": "stuck",
    }]

held = run_case(mutate=false_execution_after_hold)
assert probe_row(held)["dispatchable"] is False, held
assert probe_row(held)["status"] == "stuck", held
assert held["publicProbeRecovery"]["requiresEditorReplan"] is True, held
assert held["publicProbeRecovery"]["dispatchesUsed"] == 1, held

# An earlier genuine clock or an invalid clock cannot renew a consumed budget.
for bad_clock in ("invalid-again", "2030-01-01T00:00:00Z",
                  (NOW - timedelta(hours=6)).isoformat()):
    def regression(d, value=bad_clock):
        false_execution_after_hold(d)
        d["pages_status"]["checkedAt"] = value
    r = run_case(mutate=regression)
    assert r["publicProbeRecovery"]["budgetKey"] == stale_stamp, r
    assert probe_row(r)["dispatchable"] is False, r

def invalid_used_budget(d):
    d["pages_status"] = {"checkedAt": "future-again", "match": True}
    d["previous"] = {"publicProbeRecovery": {
        "budgetKey": "invalid-public-probe", "dispatchesUsed": 1,
        "dispatchedAt": (NOW - timedelta(minutes=11)).isoformat(),
        "lastObservationAt": None,
    }, "assignments": [], "execution": []}

r = run_case(mutate=invalid_used_budget)
assert probe_row(r)["status"] == "stuck", r
assert probe_row(r)["dispatchable"] is False, r

def genuine_advance(d):
    false_execution_after_hold(d)
    d["pages_status"] = {"checkedAt": NOW_ISO, "match": True}

r = run_case(mutate=genuine_advance)
assert r["assignments"] == [], r
assert r["publicProbeRecovery"]["budgetKey"] == NOW_ISO, r
assert r["publicProbeRecovery"]["dispatchesUsed"] == 0, r
assert r["publicProbeRecovery"]["requiresEditorReplan"] is False, r
assert r["healthy"] is True, r

# Fresh observation showing failure keeps the newsroom RED until actual repair
# and the independently owned EIC audit classify/verify the genuine mismatch.
r = run_case(mutate=lambda d: d["pages_status"].update(match=False))
assert r["assignments"] == [], r
assert r["healthy"] is False, r
r = run_case(mutate=lambda d: d["pages_status"].update(match=False), publication_rc=1)
assert r["healthy"] is False, r

workflow = (ROOT / ".github/workflows/editor-in-chief-newsroom-assignment.yml").read_text(encoding="utf-8")
assert '"Verify Public Pages Publication Snapshot"' in workflow
assert "git show origin/pages-status:data/pages-live-status.json" in workflow
assert "--pages-status /tmp/pages-live-status.json" in workflow
observer = next(x for x in registry["robots"] if x["id"] == "public-probe")
assert observer["workflow"] == "pages-probe.yml"
assert observer["readOnlyObservation"] is True
assert observer["faultClasses"] == ["public-probe-stale"]
assert observer["maxRuntimeMinutes"] == 5
def post_deployment(d):
    d["pages_status"] = {"checkedAt": (NOW - timedelta(minutes=5)).isoformat(), "match": False}
    d["pages_deployment"] = [{"conclusion": "success", "updatedAt": (NOW - timedelta(minutes=1)).isoformat()}]
    d["editor"]["findings"] = [{"code": "PUBLIC_STOCK_NOT_PROPAGATED", "area": "pages", "severity": "critical"}]

r = run_case(mutate=post_deployment)
assert {x["robot"] for x in r["assignments"]} == {"public-probe"}, r
assert r["healthy"] is False, r
assert r["publicProbeRecovery"]["requiredAfterAt"] == (NOW - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"), r
post = r
post_row = probe_row(post)

def deployment_obligation_survives(d):
    post_deployment(d)
    d["pages_deployment"] = [{"conclusion": "success", "updatedAt": "2030-01-01T00:00:00Z"}]
    d["previous"] = dict(post)
    d["previous"]["execution"] = [{"assignmentId": post_row["assignmentId"], "workflow": "pages-probe.yml", "dispatched": True}]

r = run_case(mutate=deployment_obligation_survives)
assert probe_row(r)["dispatchable"] is False, r
assert r["publicProbeRecovery"]["requiredAfterAt"] == post["publicProbeRecovery"]["requiredAfterAt"], r
assert r["healthy"] is False, r

def deployment_observed(d):
    deployment_obligation_survives(d)
    d["pages_status"] = {"checkedAt": NOW_ISO, "match": True}
    d["editor"]["findings"] = []

r = run_case(mutate=deployment_observed)
assert r["healthy"] is True, r
assert r["assignments"] == [], r
assert r["publicProbeRecovery"]["dispatchesUsed"] == 0, r
assert "--pages-deployment /tmp/pages-deployment.json" in workflow
assert "--json databaseId,conclusion,updatedAt" in workflow
print("NEWSROOM_CONTROL_PLANE_V2_TESTS_OK routing_regressions=11 public_probe_regressions=20")


