#!/usr/bin/env python3
"""Editor-in-Chief newsroom assignment engine.

The audit decides *what is wrong*. This control plane decides *which robot owns
the fault*, whether the previous assignment actually improved production, and
which stage may run next. Leaf robots never decide the next robot themselves.

Design invariants:
- config/newsroom-robots.json is the runtime source of truth for robot/workflow
  mapping, supported modes and success evidence.
- Dispatch is not success. Every assignment captures an outcome snapshot that
  the next cycle compares with current production evidence.
- No identical infinite retry. Normal mode escalates to deep when supported;
  repeated no-progress after deep (or repeated no-progress for a single-mode
  robot) becomes STUCK and requires Editor-in-Chief replanning.
- Publication stages are event-driven. Producer -> Live -> Desk Merge -> Pages
  is advanced by workflow completion re-audits, not leaf-to-leaf dispatches.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from desk_freshness_policy import current_daily_dates

HKT = timezone(timedelta(hours=8))
SOFT_TARGETS = {
    "world": 3,
    "asia": 3,
    "hong-kong": 6,
    "japan": 6,
    "market-economy": 4,
    "finance": 4,
    "ai-tech": 4,
    "manga-anime": 24,
    "manchester-united": 12,
    "football": 8,
}
CANDIDATE_MAX_AGE_HOURS = {
    "manga-anime": 48,
    "manchester-united": 48,
    "football": 48,
}
DEFAULT_CANDIDATE_MAX_AGE_HOURS = 24


def load(path: str | None, default: Any) -> Any:
    if not path:
        return default
    p = Path(path)
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def parse_iso(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def load_registry(path: str) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, str]]:
    data = load(path, {})
    robots = data.get("robots")
    if not isinstance(robots, list) or not robots:
        raise SystemExit(f"{path}: robot registry is missing/empty")
    by_id: dict[str, dict[str, Any]] = {}
    trigger_map: dict[str, str] = {}
    seen_workflows: set[str] = set()
    for row in robots:
        if not isinstance(row, dict):
            raise SystemExit(f"{path}: robot entry must be an object")
        robot_id = str(row.get("id") or "").strip()
        workflow = str(row.get("workflow") or "").strip()
        workflow_name = str(row.get("workflowName") or "").strip()
        if not robot_id or not workflow:
            raise SystemExit(f"{path}: robot id/workflow is required")
        if robot_id in by_id:
            raise SystemExit(f"{path}: duplicate robot id {robot_id}")
        if workflow in seen_workflows:
            raise SystemExit(f"{path}: duplicate workflow {workflow}")
        seen_workflows.add(workflow)
        by_id[robot_id] = row
        trigger_map[workflow] = robot_id
        if workflow_name:
            trigger_map[workflow_name] = robot_id
    return data, by_id, trigger_map


def current_candidate(item: Any, now: datetime, desk: str) -> bool:
    if not isinstance(item, dict):
        return False
    dt = parse_iso(item.get("publishedAt") or item.get("updatedAt") or item.get("timestamp"))
    if dt is None:
        return False
    max_age = CANDIDATE_MAX_AGE_HOURS.get(desk, DEFAULT_CANDIDATE_MAX_AGE_HOURS)
    return 0 <= (now - dt).total_seconds() <= max_age * 3600


def pending_live_draft(
    prepublish: dict[str, Any],
    now: datetime,
    live: dict[str, Any] | None = None,
) -> bool:
    if prepublish.get("status") != "VERIFIED_DRAFT" or prepublish.get("publicationType") != "LIVE":
        return False
    if not prepublish.get("articles"):
        return False
    draft_id = str(prepublish.get("draftId") or "").strip()
    published_draft_id = str(((live or {}).get("coverage") or {}).get("verifiedDraftId") or "").strip()
    # A verified draft that already produced the current Live snapshot is consumed.
    # Treating it as pending causes the Editor-in-Chief to redispatch the same
    # publisher forever and prevents the producer from making the next edition.
    if draft_id and published_draft_id == draft_id:
        return False
    created = parse_iso(prepublish.get("createdAt"))
    return bool(created and 0 <= (now - created).total_seconds() <= 120 * 60)


def producer_capacity_blocked(capacity: dict[str, Any], now: datetime) -> bool:
    """Fail closed while capacity telemetry still says QUOTA_EXHAUSTED.

    blockedUntil is only the earliest time at which a fresh capacity probe may
    be attempted. It is NOT proof that capacity recovered. Only an explicit
    non-exhausted status from fresh telemetry may unblock the producer.
    """
    status = str(capacity.get("status") or "").upper()
    if status in {"QUOTA_EXHAUSTED", "LOCAL_FALLBACK_FAILED"}:
        return True
    return False


def daily_recovery_required(latest: dict[str, Any], editor: dict[str, Any], now: datetime) -> bool:
    """Daily owns its edition/structure, not unrelated Live or desk failures."""
    if str(latest.get("date") or "") not in current_daily_dates(now=now):
        return True
    if any(
        isinstance(row, dict) and row.get("name") == "daily-v3" and row.get("ok") is False
        for row in (editor.get("validatorAudit") or [])
    ):
        return True
    return any(
        isinstance(row, dict) and row.get("area") == "daily" and row.get("severity") == "critical"
        for row in (editor.get("findings") or [])
    )


def sentinel_requires_deployment(sentinel: dict[str, Any], pages_workflow: str) -> bool:
    """Use sentinel ownership: an HTTP-200 editorial gap is not a deploy fault.

    Legacy/unclassified failed-page evidence remains conservative. Modern
    sentinel reports explicitly distinguish deployment from newsroom owners.
    """
    failed = sentinel.get("persistentFailedPages") or []
    if not failed:
        return False
    repairs = sentinel.get("repairWorkflows")
    if isinstance(repairs, list) and repairs:
        return pages_workflow in repairs
    return True


def make_cycle_id(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def public_probe_evidence(pages: dict[str, Any], now: datetime, required_after: datetime | None = None) -> dict[str, Any]:
    """Dispatch is not observation; invalid clocks cannot renew a budget."""
    stamp = parse_iso(pages.get("checkedAt"))
    genuine_clock = stamp is not None and stamp <= now
    age = (now - stamp).total_seconds() / 60.0 if genuine_clock else None
    normalized = stamp.isoformat().replace("+00:00", "Z") if genuine_clock else None
    return {
        "publicProbeCheckedAt": normalized,
        "publicProbeAgeMinutes": age,
        "publicProbeFresh": age is not None and age <= 30.0 and (required_after is None or stamp >= required_after),
        "publicProbeMatch": pages.get("match") is True,
        "publicProbeBudgetKey": normalized or "invalid-public-probe",
        "publicProbeRequiredAfterAt": required_after.isoformat().replace("+00:00", "Z") if required_after else None,
    }


def public_probe_recovery(previous: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    """Latch one successful Site EIC dispatch until genuine evidence advances.

    This survives already-active/blocked cycles and absent assignments. Missing,
    malformed, future or regressing telemetry cannot manufacture another budget.
    A fresh observation may still show failure: its clock is not publication.
    """
    prior = previous.get("publicProbeRecovery") or {}
    if not isinstance(prior, dict):
        prior = {}
    current_stamp = parse_iso(evidence.get("publicProbeCheckedAt"))
    prior_stamp = parse_iso(prior.get("lastObservationAt"))
    advanced = current_stamp is not None and (prior_stamp is None or current_stamp > prior_stamp)
    key = evidence["publicProbeBudgetKey"] if advanced or not prior else prior.get("budgetKey")
    key = key or "invalid-public-probe"
    same_key = prior.get("budgetKey") == key
    used = 1 if same_key and prior.get("dispatchesUsed") == 1 else 0
    dispatched_at = prior.get("dispatchedAt") if same_key else None
    for row in (previous.get("assignments") or []):
        if not isinstance(row, dict) or row.get("robot") != "public-probe" or row.get("probeBudgetKey") != key:
            continue
        if any(
            isinstance(item, dict) and item.get("workflow") == row.get("workflow")
            and item.get("dispatched") is True and item.get("assignmentId") == row.get("assignmentId")
            for item in (previous.get("execution") or [])
        ):
            used = 1
            dispatched_at = dispatched_at or previous.get("checkedAt")
    return {
        "budgetKey": key,
        "maxDispatches": 1,
        "dispatchesUsed": used,
        "dispatchedAt": dispatched_at,
        "lastObservationAt": evidence["publicProbeCheckedAt"] if advanced else prior.get("lastObservationAt"),
        "freshObservation": evidence["publicProbeFresh"],
        "requiredAfterAt": evidence["publicProbeRequiredAfterAt"],
        "requiresEditorReplan": bool(same_key and prior.get("requiresEditorReplan")),
    }


def assign_public_observation(
    plan: list[dict[str, Any]], robots: dict[str, dict[str, Any]],
    evidence: dict[str, Any], recovery: dict[str, Any], now: datetime,
    trigger_robot: str | None,
) -> None:
    if evidence["publicProbeFresh"]:
        return
    add_assignment(
        plan, robots, "public-probe", "public-probe-stale",
        "public observation is missing, invalid, older than 30 minutes or predates the latest successful deployment; verify HTTP outcomes without deploying or changing news",
    )
    row = next(item for item in plan if item["robot"] == "public-probe")
    row["probeBudgetKey"] = recovery["budgetKey"]
    row["readOnlyObservation"] = True
    row["attempt"] = recovery["dispatchesUsed"] + 1
    if recovery["dispatchesUsed"]:
        dispatched = parse_iso(recovery.get("dispatchedAt"))
        expired = (
            recovery["requiresEditorReplan"] or dispatched is None or dispatched > now
            or (now - dispatched).total_seconds() > 10 * 60
        )
        completed = trigger_robot == "public-probe"
        row["dispatchable"] = False
        row["status"] = "stuck" if expired or completed else "observation-in-flight"
        row["requiresEditorReplan"] = expired or completed
        recovery["requiresEditorReplan"] = expired or completed
        row["reason"] += "; the single dispatch budget is consumed until genuine observation evidence advances"


def add_assignment(
    plan: list[dict[str, Any]],
    robots: dict[str, dict[str, Any]],
    robot_id: str,
    fault: str,
    reason: str,
    *,
    mode: str = "normal",
    evidence: list[str] | None = None,
    desks: list[str] | None = None,
    priority: int | None = None,
) -> None:
    if robot_id not in robots:
        raise SystemExit(f"control plane tried to assign unregistered robot: {robot_id}")
    spec = robots[robot_id]
    modes = [str(x) for x in (spec.get("modes") or ["normal"])]
    if mode not in modes:
        raise SystemExit(f"robot {robot_id} does not support mode={mode}")
    supported_faults = {str(x) for x in (spec.get("faultClasses") or [])}
    if fault not in supported_faults:
        raise SystemExit(f"robot {robot_id} does not own faultClass={fault}")

    for row in plan:
        if row["robot"] == robot_id:
            if mode == "deep" and row.get("mode") != "deep":
                row["mode"] = "deep"
                row["faultClass"] = fault
                row["reason"] = reason
                mode_input = str(spec.get("modeInput") or "").strip()
                row["dispatchInputs"] = {mode_input: "deep"} if mode_input else {}
            if desks:
                row["desks"] = sorted(set((row.get("desks") or []) + desks))
            if evidence:
                row["verifyNextCycle"] = list(dict.fromkeys((row.get("verifyNextCycle") or []) + evidence))
            row["priority"] = min(int(row.get("priority") or 999), int(priority or spec.get("priority") or 50))
            return

    dispatch_inputs: dict[str, str] = {}
    mode_input = str(spec.get("modeInput") or "").strip()
    if mode_input:
        dispatch_inputs[mode_input] = mode

    plan.append(
        {
            "robot": robot_id,
            "workflow": spec["workflow"],
            "workflowName": spec.get("workflowName"),
            "job": spec.get("job"),
            "priority": int(priority or spec.get("priority") or 50),
            "maxRuntimeMinutes": int(spec.get("maxRuntimeMinutes") or 30),
            "mode": mode,
            "dispatchInputs": dispatch_inputs,
            "faultClass": fault,
            "reason": reason,
            "desks": desks or [],
            "verifyNextCycle": evidence or list(spec.get("successEvidence") or []),
            "status": "assigned",
            "dispatchable": True,
            "blockedBy": [],
        }
    )


def evidence_snapshot(
    *,
    now: datetime,
    staging: dict[str, Any],
    prepublish: dict[str, Any],
    freshness: dict[str, Any],
    latest: dict[str, Any],
    live: dict[str, Any],
    desk: dict[str, Any],
    stocks: dict[str, Any],
    tts: dict[str, Any],
    sentinel: dict[str, Any],
    stock_rc: int,
    publication_rc: int,
    vocab_ok: bool,
) -> dict[str, Any]:
    stale = []
    desk_ages: dict[str, Any] = {}
    for slug, row in (freshness.get("desks") or {}).items():
        if not isinstance(row, dict):
            continue
        desk_ages[slug] = row.get("newestAgeHours")
        soft = SOFT_TARGETS.get(slug, 6)
        age = row.get("newestAgeHours")
        hard_bad = (not row.get("fresh", False)) or (not row.get("dailySynced", True))
        soft_bad = isinstance(age, (int, float)) and age > soft
        if hard_bad or soft_bad:
            stale.append(slug)

    failed_pages = sorted(set(sentinel.get("persistentFailedPages") or []))
    return {
        "capturedAt": now.isoformat().replace("+00:00", "Z"),
        "stagingLastSearchAt": staging.get("lastSearchAt") or staging.get("lastSearchStartedAt"),
        "underfilledDesks": sorted((staging.get("underfilledDesks") or {}).keys())
        if isinstance(staging.get("underfilledDesks"), dict)
        else [],
        "pendingLiveDraft": pending_live_draft(prepublish, now, live),
        "prepublishDraftId": prepublish.get("draftId"),
        "prepublishCreatedAt": prepublish.get("createdAt"),
        "latestDate": latest.get("date"),
        "liveLastUpdated": live.get("lastUpdated"),
        "deskGeneratedAt": desk.get("generatedAt") or desk.get("lastUpdated"),
        "staleDesks": sorted(stale),
        "deskNewestAgeHours": desk_ages,
        "stockGeneratedAt": stocks.get("generatedAt"),
        "stockLastCheckedAt": stocks.get("lastCheckedAt"),
        "stockValidatorOk": stock_rc == 0,
        "publicationValidatorOk": publication_rc == 0,
        "vocabTodayOk": vocab_ok,
        "failedPages": failed_pages,
        "sentinelCheckedAt": sentinel.get("checkedAt"),
        "voicePending": int(tts.get("pendingArticleCount") or 0),
        "voiceCoverageComplete": bool(tts.get("coverageComplete")),
    }


def execution_for(previous: dict[str, Any], workflow: str) -> dict[str, Any] | None:
    rows = previous.get("execution") or []
    for row in rows:
        if isinstance(row, dict) and row.get("workflow") == workflow:
            return row
    return None


def made_progress(robot: str, before: dict[str, Any], current: dict[str, Any]) -> bool | None:
    if not before:
        return None
    if robot == "collector":
        return (
            current.get("stagingLastSearchAt") != before.get("stagingLastSearchAt")
            or len(current.get("underfilledDesks") or []) < len(before.get("underfilledDesks") or [])
        )
    if robot == "general-producer":
        return (
            current.get("prepublishDraftId") not in {None, before.get("prepublishDraftId")}
            or (
                current.get("pendingLiveDraft") is True
                and before.get("pendingLiveDraft") is not True
            )
            or len(current.get("staleDesks") or []) < len(before.get("staleDesks") or [])
        )
    if robot == "live-publisher":
        return current.get("liveLastUpdated") not in {None, before.get("liveLastUpdated")}
    if robot == "desk-merge":
        return (
            current.get("deskGeneratedAt") not in {None, before.get("deskGeneratedAt")}
            or len(current.get("staleDesks") or []) < len(before.get("staleDesks") or [])
        )
    if robot == "stock":
        return bool(current.get("stockValidatorOk")) or (
            current.get("stockGeneratedAt") not in {None, before.get("stockGeneratedAt")}
            or current.get("stockLastCheckedAt") not in {None, before.get("stockLastCheckedAt")}
        )
    if robot == "vocab":
        return bool(current.get("vocabTodayOk"))
    if robot == "daily-recovery":
        return bool(current.get("publicationValidatorOk")) and current.get("latestDate") != before.get("latestDate")
    if robot == "pages":
        return (
            len(current.get("failedPages") or []) < len(before.get("failedPages") or [])
            or (
                current.get("sentinelCheckedAt") not in {None, before.get("sentinelCheckedAt")}
                and not current.get("failedPages")
            )
        )
    if robot == "voice":
        return bool(current.get("voiceCoverageComplete")) or int(current.get("voicePending") or 0) < int(before.get("voicePending") or 0)
    return None


def apply_previous_outcomes(
    plan: list[dict[str, Any]],
    robots: dict[str, dict[str, Any]],
    previous: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    now: datetime,
    trigger_robot: str | None,
) -> None:
    previous_rows = {
        str(row.get("robot")): row
        for row in (previous.get("assignments") or [])
        if isinstance(row, dict) and row.get("robot")
    }
    for row in plan:
        if row["robot"] in {"public-probe", "daily-recovery"}:
            # Durable observation/material-input ledgers own these budgets;
            # generic retries must not reset a held or exhausted epoch.
            row["outcomeBefore"] = snapshot
            continue
        if row.get("status") == "awaiting-reviewed-editorial-trial-outcome":
            # Read-only proof of the sole active bound child is ownership, not
            # admission or a completed retry. Never charge or dispatch here.
            row["outcomeBefore"] = snapshot
            continue
        prior = previous_rows.get(row["robot"])
        row["attempt"] = 1
        row["outcomeBefore"] = snapshot
        if row.get("status") == "reviewed-editorial-trial":
            # This is a different reviewed behavior, with its own durable,
            # create-only semantic claim. The prior normal-path retry counter
            # is audit evidence, not authority to consume the new trial budget.
            if prior:
                row["previousOutcome"] = {
                    "cycleId": previous.get("cycleId"),
                    "progress": made_progress(row["robot"], prior.get("outcomeBefore") or {}, snapshot),
                    "mode": prior.get("mode"),
                    "attempt": prior.get("attempt", 1),
                    "evaluation": "reviewed-semantic-trial-separate-from-prior-path",
                }
            continue
        if str(row.get("status") or "").startswith("external-failover"):
            prior_attempt = int((prior or {}).get("attempt") or 1)
            before_live = ((prior or {}).get("outcomeBefore") or {}).get("liveLastUpdated")
            current_live = snapshot.get("liveLastUpdated")
            progress = bool(before_live and current_live and current_live != before_live)
            if row.get("status") == "external-failover-stuck":
                row["attempt"] = prior_attempt + 1 if prior else 1
                row["previousOutcome"] = {
                    "cycleId": previous.get("cycleId"),
                    "progress": progress,
                    "mode": (prior or {}).get("mode"),
                    "attempt": prior_attempt,
                    "evaluation": "external-publisher-no-progress" if not progress else "external-capacity-failover",
                }
            elif prior:
                row["attempt"] = prior_attempt
                row["previousOutcome"] = {
                    "cycleId": previous.get("cycleId"),
                    "progress": progress if before_live else None,
                    "mode": prior.get("mode"),
                    "attempt": prior_attempt,
                    "evaluation": "external-capacity-failover",
                }
            continue
        if not prior:
            continue
        execution = execution_for(previous, row["workflow"])
        # "already-active" is ownership evidence, not a completed attempt. Never
        # escalate a healthy in-flight robot merely because its output has not
        # appeared yet.
        if not execution or not execution.get("dispatched"):
            continue

        previous_checked = parse_iso(previous.get("checkedAt"))
        max_runtime = float(prior.get("maxRuntimeMinutes") or robots[row["robot"]].get("maxRuntimeMinutes") or 30)
        runtime_expired = bool(
            previous_checked
            and (now - previous_checked).total_seconds() / 60.0 > max_runtime + 5.0
        )
        completed_event = trigger_robot == row["robot"]
        if not completed_event and not runtime_expired:
            row["previousOutcome"] = {
                "cycleId": previous.get("cycleId"),
                "progress": None,
                "mode": prior.get("mode"),
                "attempt": prior.get("attempt", 1),
                "evaluation": "deferred-in-flight",
            }
            continue

        progress = made_progress(row["robot"], prior.get("outcomeBefore") or {}, snapshot)
        row["previousOutcome"] = {
            "cycleId": previous.get("cycleId"),
            "progress": progress,
            "mode": prior.get("mode"),
            "attempt": prior.get("attempt", 1),
        }
        if progress is not False:
            continue

        row["attempt"] = int(prior.get("attempt") or 1) + 1
        spec = robots[row["robot"]]
        modes = [str(x) for x in (spec.get("modes") or ["normal"])]
        prior_mode = str(prior.get("mode") or "normal")
        if "deep" in modes and prior_mode != "deep":
            row["mode"] = "deep"
            mode_input = str(spec.get("modeInput") or "").strip()
            row["dispatchInputs"] = {mode_input: "deep"} if mode_input else {}
            row["reason"] += "; previous assigned path made no measurable progress, escalating to deep mode"
            row["faultClass"] = "stock-no-progress" if row["robot"] == "stock" else row["faultClass"]
            row["status"] = "escalated"
        elif row["attempt"] >= 3:
            row["dispatchable"] = False
            row["status"] = "stuck"
            row["requiresEditorReplan"] = True
            row["reason"] += "; repeated assigned path made no measurable progress and identical retry is blocked"


def block_downstream_races(plan: list[dict[str, Any]]) -> None:
    by_id = {row["robot"]: row for row in plan}
    if "desk-merge" in by_id:
        blockers = [x for x in ("daily-recovery", "general-producer", "live-publisher") if x in by_id and by_id[x].get("dispatchable")]
        if blockers:
            row = by_id["desk-merge"]
            row["blockedBy"] = blockers
            row["dispatchable"] = False
            if row.get("status") != "stuck":
                row["status"] = "blocked"

    # Pages is deliberately NOT blocked by Stock/Vocab/newsroom repair jobs.
    # A stale Stock subsystem must never freeze deployment of a valid new Live,
    # Daily or Desk snapshot. Any later main-branch repair will trigger another
    # Pages deployment, so allowing Pages to publish the current repository
    # state is safer than coupling unrelated subsystems behind one global gate.


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", default="config/newsroom-robots.json")
    ap.add_argument("--staging", required=True)
    ap.add_argument("--prepublish")
    ap.add_argument("--producer-capacity")
    ap.add_argument("--freshness", required=True)
    ap.add_argument("--editor-status", required=True)
    ap.add_argument("--sentinel", required=True)
    ap.add_argument("--pages-status", default="/tmp/pages-live-status.json")
    ap.add_argument("--pages-deployment")
    ap.add_argument("--editorial-trial", help="Site EIC inspected one-trial admission; immutable claim is still required")
    ap.add_argument("--previous-assignments")
    ap.add_argument("--latest", default="data/latest.json")
    ap.add_argument("--live", default="data/live.json")
    ap.add_argument("--desk", default="data/desk-latest.json")
    ap.add_argument("--stocks", default="data/stocks-latest.json")
    ap.add_argument("--tts", default="data/tts-manifest.json")
    ap.add_argument("--stock-rc", type=int, required=True)
    ap.add_argument("--publication-rc", type=int, required=True)
    ap.add_argument("--vocab-rc", type=int, required=True)
    ap.add_argument("--trigger-workflow", default="")
    ap.add_argument("--trigger-conclusion", default="")
    ap.add_argument("--now", help="ISO timestamp, test-only")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    now = parse_iso(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        raise SystemExit("invalid --now")

    registry, robots, trigger_map = load_registry(args.registry)
    staging = load(args.staging, {})
    prepublish = load(args.prepublish, {})
    producer_capacity = load(args.producer_capacity, {})
    freshness = load(args.freshness, {})
    editor = load(args.editor_status, {})
    sentinel = load(args.sentinel, {})
    pages = load(args.pages_status, {})
    if not isinstance(pages, dict):
        pages = {}
    previous = load(args.previous_assignments, {})
    trial_permit = load(args.editorial_trial, {})
    latest = load(args.latest, {})
    live = load(args.live, {})
    desk = load(args.desk, {})
    stocks = load(args.stocks, {})
    tts = load(args.tts, {})

    today_hkt = now.astimezone(HKT).date().isoformat()
    vocab_ok = args.vocab_rc == 0
    snapshot = evidence_snapshot(
        now=now,
        staging=staging,
        prepublish=prepublish,
        freshness=freshness,
        latest=latest,
        live=live,
        desk=desk,
        stocks=stocks,
        tts=tts,
        sentinel=sentinel,
        stock_rc=args.stock_rc,
        publication_rc=args.publication_rc,
        vocab_ok=vocab_ok,
    )
    producer_blocked = producer_capacity_blocked(producer_capacity, now)
    from daily_recovery_dependency import daily_budget, inspect_daily_dependency, public_daily_evidence
    import build_today_daily_from_desk as daily_builder
    import validate_desk_integrity as desk_integrity
    integrity_state, integrity_detail = desk_integrity.inspect(Path(args.desk), Path(args.live))
    daily_input = inspect_daily_dependency(
        now=now, desk=desk, live=live, builder=daily_builder,
        integrity_state=integrity_state, integrity_detail=integrity_detail,
    )
    daily_recovery_state, daily_decision = daily_budget(previous, daily_input)
    snapshot["dailyRecoveryInputEvidence"] = public_daily_evidence(daily_input)
    # A successful deployment is not an independent observation. Retain the
    # latest real deployment clock across blocked/unassigned cycles; neither
    # missing metadata nor regressing/future clocks can erase this obligation.
    prior_probe = previous.get("publicProbeRecovery") or {}
    deployment_rows = load(args.pages_deployment, [])
    deployment_clocks = [parse_iso(prior_probe.get("requiredAfterAt"))] if isinstance(prior_probe, dict) else []
    if isinstance(deployment_rows, list):
        deployment_clocks += [parse_iso(row.get("updatedAt")) for row in deployment_rows
                              if isinstance(row, dict) and row.get("conclusion") == "success"]
    valid_deployments = [clock for clock in deployment_clocks if clock is not None and clock <= now]
    required_after = max(valid_deployments) if valid_deployments else None
    probe_evidence = public_probe_evidence(pages, now, required_after)
    snapshot.update(probe_evidence)
    probe_recovery = public_probe_recovery(previous, probe_evidence)
    snapshot["producerCapacityStatus"] = producer_capacity.get("status")
    snapshot["producerCapacityCheckedAt"] = producer_capacity.get("checkedAt")
    snapshot["producerCapacityBlockedUntil"] = producer_capacity.get("blockedUntil")
    snapshot["producerCapacityBlocked"] = producer_blocked

    trigger_robot = trigger_map.get(args.trigger_workflow)
    trigger_success = bool(trigger_robot and args.trigger_conclusion == "success")
    plan: list[dict[str, Any]] = []
    assign_public_observation(plan, robots, probe_evidence, probe_recovery, now, trigger_robot)

    # 1) Discovery health: timestamp freshness alone is never enough.
    stamp = parse_iso(staging.get("lastSearchAt") or staging.get("lastSearchStartedAt"))
    age = 999999.0 if stamp is None else max(0.0, (now - stamp).total_seconds() / 60.0)
    underfilled = staging.get("underfilledDesks") if isinstance(staging.get("underfilledDesks"), dict) else {}
    query_audit = staging.get("queryAudit") if isinstance(staging.get("queryAudit"), dict) else {}
    floor_failed = sorted(
        desk_name
        for desk_name, row in query_audit.items()
        if isinstance(row, dict) and int(row.get("floorMetThisRun") or 0) != 1
    )
    discovery_bad = sorted(set(underfilled) | set(floor_failed))
    collector_duty = robots["collector"].get("standingDuty") or {}
    collector_due = float(collector_duty.get("dueAfterMinutes") or 12)
    if age > 25:
        add_assignment(
            plan,
            robots,
            "collector",
            "collection-stale",
            f"discovery staging is {age:.1f} minutes old",
            evidence=["lastSearchAt advances", "collector run completes"],
        )
    elif age >= collector_due:
        add_assignment(
            plan,
            robots,
            "collector",
            "collection-duty",
            f"standing 15-minute discovery duty is due; staging age is {age:.1f} minutes",
            evidence=["lastSearchAt advances", "collector run completes"],
        )
    if discovery_bad:
        add_assignment(
            plan,
            robots,
            "collector",
            "discovery-underfilled",
            "current collection completed but desk discovery outcome is under target",
            mode="deep",
            desks=discovery_bad,
            evidence=["underfilledDesks reduced or cleared", "queryAudit.floorMetThisRun=1 for affected desks"],
        )

    # 2) Published desk health: classify discovery shortage vs verification/copy bottleneck.
    stale_desks: list[str] = []
    stale_with_candidates: list[str] = []
    stale_without_candidates: list[str] = []
    for desk_name, row in (freshness.get("desks") or {}).items():
        if not isinstance(row, dict):
            continue
        ageh = row.get("newestAgeHours")
        hard_bad = (not row.get("fresh", False)) or (not row.get("dailySynced", True))
        soft = SOFT_TARGETS.get(desk_name, 6)
        soft_bad = isinstance(ageh, (int, float)) and ageh > soft
        if not (hard_bad or soft_bad):
            continue
        stale_desks.append(desk_name)
        staging_key = "finance" if desk_name == "market-economy" else desk_name
        candidates = (staging.get("desks") or {}).get(staging_key) or []
        usable = [x for x in candidates if current_candidate(x, now, desk_name)]
        if usable:
            stale_with_candidates.append(desk_name)
        else:
            stale_without_candidates.append(desk_name)

    if stale_without_candidates:
        add_assignment(
            plan,
            robots,
            "collector",
            "discovery-missing-for-stale-desk",
            "published desks are stale and staging has no usable current candidates",
            mode="deep",
            desks=stale_without_candidates,
            evidence=["affected desks gain current candidates", "query floor satisfied"],
        )

    pending_draft = pending_live_draft(prepublish, now, live)
    if stale_with_candidates:
        if trigger_success and trigger_robot in {"live-publisher", "daily-recovery"}:
            add_assignment(
                plan,
                robots,
                "desk-merge",
                "desk-freshness-gap",
                "upstream publication completed; Rolling Desk must consume the new verified snapshot",
                desks=stale_with_candidates,
            )
        elif pending_draft:
            add_assignment(
                plan,
                robots,
                "live-publisher",
                "pending-live-draft",
                "a verified Live draft already exists; publish it before producing more copy",
                desks=stale_with_candidates,
            )
        else:
            add_assignment(
                plan,
                robots,
                "general-producer",
                "desk-stale-with-candidates",
                "staging already has current candidates; verification/copy conversion is the bottleneck",
                desks=stale_with_candidates,
            )

    # 3) Live publication: if no verified draft exists, do not ask the publisher to invent one.
    live_stale = any(
        isinstance(f, dict) and f.get("code") in {"LIVE_STALE", "PERSISTENT_LIVE_STALE"}
        for f in (editor.get("findings") or [])
    )
    if live_stale:
        if pending_draft:
            add_assignment(
                plan,
                robots,
                "live-publisher",
                "live-stale",
                "Editor-in-Chief reports Live stale and a verified draft is ready",
            )
        elif stale_with_candidates or any((staging.get("desks") or {}).values()):
            add_assignment(
                plan,
                robots,
                "general-producer",
                "live-stale-with-candidates",
                "Live is stale but no verified draft exists; verification/production must run first",
                desks=stale_with_candidates,
            )
        else:
            add_assignment(
                plan,
                robots,
                "collector",
                "live-stale-no-draft",
                "Live is stale, no verified draft exists and discovery has no usable reservoir",
                mode="deep",
            )

    # 4) Event-driven newsroom handoff. Leaf robots never dispatch the next leaf.
    if trigger_robot == "general-producer" and args.trigger_conclusion == "success" and pending_draft:
        add_assignment(
            plan,
            robots,
            "live-publisher",
            "pending-live-draft",
            "General News Producer completed and left a verified Live draft ready for publication",
            priority=15,
        )
    if (
        trigger_robot == "general-producer"
        and args.trigger_conclusion
        and args.trigger_conclusion != "success"
        and not producer_blocked
    ):
        add_assignment(
            plan,
            robots,
            "collector",
            "producer-exhausted",
            "General News Producer completed without a successful publishable outcome; refresh discovery via a different path",
            mode="deep",
            desks=stale_desks,
        )
    if trigger_success and trigger_robot in {"live-publisher", "daily-recovery"}:
        add_assignment(
            plan,
            robots,
            "desk-merge",
            "daily-recovery-complete" if trigger_robot == "daily-recovery" else "live-newer-than-desk",
            "verified upstream publication completed; canonical Rolling Desk must be rebuilt from repository state",
            priority=20,
        )
    if trigger_success and trigger_robot in {"desk-merge", "stock", "vocab"}:
        add_assignment(
            plan,
            robots,
            "pages",
            "upstream-publication-complete",
            f"{trigger_robot} completed successfully; deploy the exact validated repository state",
            priority=20,
        )

    # Daily needs a genuinely current verified Desk and eight Daily-safe stories.
    # Resolve this prerequisite before writer/race checks so a waiting Daily
    # cannot prevent newer verified Live from reaching Desk Merge.
    if daily_recovery_required(latest, editor, now):
        add_assignment(
            plan, robots, "daily-recovery", "daily-currentness",
            "repository Daily edition/currentness or Daily structure failed",
        )
        daily_row = next(row for row in plan if row["robot"] == "daily-recovery")
        daily_row.update(daily_decision)
        daily_row["blockedBy"] = ["verified-current-rolling-desk"] if not daily_input["ready"] else []
        if str(latest.get("date") or "") >= daily_input["requiredEdition"]:
            # This builder only recovers a stale edition; its current-edition
            # NOOP cannot repair malformed current copy. Escalate honestly,
            # rather than repeatedly dispatch or pretend Desk is the blocker.
            daily_row.update(
                status="stuck", dispatchable=False, requiresEditorReplan=True,
                blockedBy=[], reason="current-daily-structural-fault-not-repairable-by-stale-edition-builder",
            )

    # A newer Live snapshot with no upstream writer currently assigned belongs to Desk Merge.
    live_dt = parse_iso(live.get("lastUpdated"))
    desk_dt = parse_iso(desk.get("generatedAt") or desk.get("lastUpdated"))
    if live_dt and (desk_dt is None or live_dt > desk_dt) and not any(
        row["robot"] in {"general-producer", "live-publisher", "daily-recovery"}
        and row.get("dispatchable")
        for row in plan
    ):
        add_assignment(
            plan,
            robots,
            "desk-merge",
            "live-newer-than-desk",
            "repository Live snapshot is newer than canonical Rolling Desk",
        )

    # 5) Stock has an Editor-in-Chief-owned hourly standing duty. Its legacy
    # quiet windows remain 01:00-05:59 HKT plus the 08:00 Daily handover hour.
    stock_duty = robots["stock"].get("standingDuty") or {}
    active_hours = stock_duty.get("activeHoursHKT") or []
    stock_check = parse_iso(stocks.get("lastCheckedAt") or stocks.get("generatedAt"))
    stock_age = 999999.0 if stock_check is None else max(0.0, (now - stock_check).total_seconds() / 60.0)
    stock_due = float(stock_duty.get("dueAfterMinutes") or 50)
    if (
        args.stock_rc == 0
        and isinstance(active_hours, list)
        and now.astimezone(HKT).hour in {int(x) for x in active_hours}
        and stock_age >= stock_due
    ):
        add_assignment(
            plan,
            robots,
            "stock",
            "stock-duty",
            f"standing hourly Stock review duty is due; last check age is {stock_age:.1f} minutes",
        )

    # Validator failures override a routine duty and may escalate to deep mode.
    deep_stock = any(
        isinstance(x, dict) and x.get("area") == "stock-deep"
        for x in (editor.get("repairPlan") or [])
    ) or any(
        isinstance(f, dict) and f.get("code") == "STOCK_RECOVERY_NO_PROGRESS"
        for f in (editor.get("findings") or [])
    )
    if args.stock_rc != 0:
        add_assignment(
            plan,
            robots,
            "stock",
            "stock-no-progress" if deep_stock else "stock-stale",
            "Stock validator failed; use alternate deep path after no measurable prior progress"
            if deep_stock
            else "Stock validator failed",
            mode="deep" if deep_stock else "normal",
        )

    # 6) Vocab is TODAY-only. Historical gaps never block today's file.
    if not vocab_ok:
        add_assignment(
            plan,
            robots,
            "vocab",
            "vocab-stale",
            f"today's HKT vocab contract failed for {today_hkt}",
        )

    # 7) Daily/current publication.
    failed_pages = set(sentinel.get("persistentFailedPages") or [])
    # Daily was planned above, before dependency/race checks.

    # 8) Pages/public propagation. This robot deploys; it does not rebuild newsroom data.
    page_fault = any(
        isinstance(f, dict)
        and f.get("code") not in {"PUBLIC_PROBE_STALE", "PERSISTENT_PUBLIC_PROBE_STALE"}
        and (f.get("area") == "pages" or str(f.get("code", "")).startswith("PUBLIC_"))
        and f.get("severity") == "critical"
        for f in (editor.get("findings") or [])
    )
    if sentinel_requires_deployment(sentinel, str(robots["pages"]["workflow"])) or (page_fault and probe_evidence["publicProbeFresh"]):
        add_assignment(
            plan,
            robots,
            "pages",
            "public-mismatch",
            "public Pages/probe remains stale or mismatched",
        )

    # 9) Voice is asynchronous and independent of text publication.
    voice = editor.get("voiceWorkflowAudit") or {}
    if not voice.get("coverageComplete", True):
        add_assignment(
            plan,
            robots,
            "voice",
            "voice-backlog",
            "voice coverage is incomplete",
        )

    snapshot["staleDesks"] = sorted(stale_desks)

    if producer_blocked:
        from editorial_revision_trial import CONTRACT_REVISION, FAILED_CAPACITY_SHA
        trial_checked = parse_iso(trial_permit.get("checkedAt")) if isinstance(trial_permit, dict) else None
        trial_eligible = bool(
            isinstance(trial_permit, dict) and trial_permit.get("eligible") is True
            and trial_permit.get("owner") == "Site Editor-in-Chief"
            and trial_permit.get("contractRevision") == CONTRACT_REVISION
            and trial_permit.get("capacitySHA") == FAILED_CAPACITY_SHA
            and trial_permit.get("priorCapacity") == producer_capacity
            and trial_permit.get("capacityRemainsFailed") is True
            and trial_permit.get("publicationPermissionGranted") is False
            and str(trial_permit.get("dispatcherRunId") or "").isdigit()
            and trial_checked is not None and 0 <= (now - trial_checked).total_seconds() <= 300
        )
        trial_expires = parse_iso(trial_permit.get("trialExpiresAt")) if isinstance(trial_permit, dict) else None
        trial_claimed = parse_iso(trial_permit.get("trialClaimedAt")) if isinstance(trial_permit, dict) else None
        trial_pending = bool(
            isinstance(trial_permit, dict) and trial_permit.get("eligible") is False
            and trial_permit.get("pending") is True
            and trial_permit.get("owner") == "Site Editor-in-Chief"
            and trial_permit.get("contractRevision") == CONTRACT_REVISION
            and trial_permit.get("capacitySHA") == FAILED_CAPACITY_SHA
            and trial_permit.get("priorCapacity") == producer_capacity
            and trial_permit.get("capacityRemainsFailed") is True
            and trial_permit.get("publicationPermissionGranted") is False
            and type(trial_permit.get("trialRunAttempt")) is int and trial_permit["trialRunAttempt"] == 1
            and trial_permit.get("trialChildStatus") in {"queued", "in_progress", "waiting", "requested", "pending"}
            and all(re.fullmatch(r"[1-9][0-9]*", str(trial_permit.get(field) or ""))
                    for field in ("trialDispatcherRunId", "trialChildRunId"))
            and all(isinstance(trial_permit.get(field), str) and bool(trial_permit[field])
                    for field in ("trialClaimSHA", "trialBindingSHA"))
            and trial_checked is not None and 0 <= (now - trial_checked).total_seconds() <= 300
            and trial_claimed is not None and trial_expires is not None
            and trial_claimed <= trial_checked <= now <= trial_expires
            and (trial_expires - trial_claimed).total_seconds() == 1200
        )
        hkt_now = now.astimezone(HKT)
        active_live_hour = hkt_now.hour in {0, 6, 7} or 9 <= hkt_now.hour <= 23
        live_stamp = parse_iso(snapshot.get("liveLastUpdated"))
        live_hkt = live_stamp.astimezone(HKT) if live_stamp else None
        live_slot_current = bool(
            live_hkt
            and live_hkt.date() == hkt_now.date()
            and live_hkt.hour == hkt_now.hour
        )
        external_slot_due = active_live_hour and hkt_now.minute >= 10
        snapshot["externalPublisherExpectedSlot"] = (
            f"{hkt_now.date().isoformat()}T{hkt_now.hour:02d}:00+08:00"
            if active_live_hour
            else None
        )
        snapshot["externalPublisherSlotCurrent"] = (
            live_slot_current if active_live_hour else None
        )
        snapshot["externalPublisherNoProgress"] = bool(
            external_slot_due and not live_slot_current and not (trial_pending or trial_eligible)
        )
        snapshot["reviewedEditorialTrialPending"] = trial_pending

        for row in plan:
            if row.get("robot") != "general-producer":
                continue
            if trial_pending:
                row.update(
                    faultClass="reviewed-editorial-code-trial",
                    status="awaiting-reviewed-editorial-trial-outcome", dispatchable=False,
                    blockedBy=[], requiresExternalPublisher=False, requiresEditorReplan=False,
                    reason="Site EIC's sole immutable-bound child is still active within its fixed expiry; failed capacity and publication gates remain held",
                    trialChildRunId=trial_permit["trialChildRunId"],
                    trialExpiresAt=trial_permit["trialExpiresAt"],
                    verifyNextCycle=["observe exact bound child result without redispatch",
                                     "strict new persisted draft proof or fail-closed terminal result"],
                )
                row.pop("dispatchInputs", None)
                continue
            if trial_eligible and producer_capacity.get("status") == "LOCAL_FALLBACK_FAILED":
                row.update(
                    faultClass="reviewed-editorial-code-trial", status="reviewed-editorial-trial",
                    dispatchable=True, blockedBy=[], requiresExternalPublisher=False,
                    reason="Site EIC permits one reviewed structured-copy revision trial; failed capacity remains held and immutable claim/child binding precede production",
                    dispatchInputs={"editorial_trial_contract": CONTRACT_REVISION,
                                    "editorial_trial_dispatcher_run": trial_permit["dispatcherRunId"]},
                    verifyNextCycle=["immutable claim and single child binding exist",
                                     "strict producer creates and persists genuinely new VERIFIED_DRAFT",
                                     "failed capacity changes only after exact persisted draft proof"],
                )
                continue
            row["faultClass"] = "producer-capacity-exhausted"
            row["status"] = "external-failover"
            row["dispatchable"] = False
            row["blockedBy"] = ["automation:Newsroom Publisher"]
            row["requiresExternalPublisher"] = True
            row["reason"] = (
                "GitHub Copilot producer capacity is exhausted; the existing "
                "Newsroom Publisher owns the alternate verified production path "
                "until the capacity probe window expires"
            )
            row["verifyNextCycle"] = [
                "prepublishDraftId advances via alternate verified production",
                "liveLastUpdated advances into the current scheduled HKT slot",
                "producer capacity later returns AVAILABLE",
            ]
            if external_slot_due and not live_slot_current:
                row["faultClass"] = "external-publisher-no-progress"
                row["status"] = "external-failover-stuck"
                row["requiresEditorReplan"] = True
                row["reason"] = (
                    "GitHub Copilot producer capacity is exhausted and the external "
                    "Newsroom Publisher did not advance Live into the current scheduled "
                    f"{hkt_now.hour:02d}:00 HKT slot by minute {hkt_now.minute:02d}; "
                    "closed-loop recovery must re-invoke or replace the external path"
                )
                row["verifyNextCycle"] = [
                    "liveLastUpdated advances into the current scheduled HKT slot",
                    "a new material Live commit exists on main",
                    "downstream Desk Merge / Pages / Discord outcome becomes current",
                ]

    apply_previous_outcomes(
        plan,
        robots,
        previous,
        snapshot,
        now=now,
        trigger_robot=trigger_robot,
    )
    block_downstream_races(plan)

    cycle_id = make_cycle_id(now)
    for row in plan:
        token = f"{cycle_id}|{row['robot']}|{row['faultClass']}|{','.join(row.get('desks') or [])}"
        row["assignmentId"] = hashlib.sha1(token.encode("utf-8")).hexdigest()[:16]
    plan.sort(key=lambda row: (int(row.get("priority") or 999), row["robot"]))

    result = {
        "schemaVersion": 2,
        "cycleId": cycle_id,
        "checkedAt": now.isoformat().replace("+00:00", "Z"),
        "role": "Editor-in-Chief",
        "dispatcher": registry.get("controlPlane", {}).get("dispatcherWorkflow"),
        "trigger": {
            "workflow": args.trigger_workflow or None,
            "robot": trigger_robot,
            "conclusion": args.trigger_conclusion or None,
        },
        "evidenceSnapshot": snapshot,
        "publicProbeRecovery": probe_recovery,
        "dailyRecoveryInput": daily_recovery_state,
        "collectorAgeMinutes": round(age, 1),
        "stockCheckAgeMinutes": round(stock_age, 1),
        "standingDuty": {
            "collectorDueAfterMinutes": collector_due,
            "stockDueAfterMinutes": stock_due,
            "stockActiveThisHourHKT": bool(
                isinstance(active_hours, list)
                and now.astimezone(HKT).hour in {int(x) for x in active_hours}
            ),
        },
        "discoveryUnderfilledDesks": discovery_bad,
        "publishedStaleDesks": sorted(stale_desks),
        "staleDesksWithCandidates": sorted(stale_with_candidates),
        "staleDesksWithoutCandidates": sorted(stale_without_candidates),
        "assignments": plan,
        "dispatchableCount": sum(1 for row in plan if row.get("dispatchable")),
        "blockedCount": sum(1 for row in plan if row.get("status") == "blocked"),
        "stuckCount": sum(
            1 for row in plan
            if row.get("status") in {"stuck", "external-failover-stuck"}
        ),
        "externalPublisherNoProgress": any(
            row.get("faultClass") == "external-publisher-no-progress"
            for row in plan
        ),
        "healthy": (
            len(plan) == 0
            and args.stock_rc == 0
            and args.publication_rc == 0
            and args.vocab_rc == 0
            and probe_evidence["publicProbeFresh"]
            and probe_evidence["publicProbeMatch"]
            and not any(
                isinstance(f, dict) and f.get("severity") == "critical"
                for f in (editor.get("findings") or [])
            )
            and not (sentinel.get("persistentFailedPages") or [])
        ),
    }
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


