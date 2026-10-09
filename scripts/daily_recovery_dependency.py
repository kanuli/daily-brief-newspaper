"""Site EIC Daily input preflight and persistent material-input retry budget.

Never writes news, calls a model, or dispatches a workflow. The production
builder and validators remain authoritative and are not modified here.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

HKT = timezone(timedelta(hours=8))
MAX_ATTEMPTS = 3
MATERIAL_FIELDS = (
    "id", "desk", "deskSlugs", "section", "sectionLabel", "title", "dek",
    "summary", "body", "context", "why", "watchNext", "sourceName", "sourceUrl",
)


def parse_time(value):
    try:
        stamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return stamp.astimezone(timezone.utc) if stamp.tzinfo else None
    except (TypeError, ValueError):
        return None


def story_material(story):
    """Source/copy identity only; no retry from clocks, status, or repository HEAD."""
    value = {name: story.get(name) for name in MATERIAL_FIELDS if name in story}
    if isinstance(story.get("sources"), list):
        value["sources"] = [
            {name: source.get(name) for name in ("name", "url", "facts") if name in source}
            for source in story["sources"] if isinstance(source, dict)
        ]
    return value


def material_hash(story, slug):
    """Clock/ID-independent copy, source and canonical routing identity.

    Selection can change when a timestamp or an ID is edited. Such a change
    is not genuinely new editorial material and must not mint another budget.
    The enclosing canonical desk is included even if a story omits its desk.
    """
    value = story_material(story)
    value.pop("id", None)
    material = {"canonicalDesk": slug, "story": value}
    return hashlib.sha256(json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def input_fingerprint(target_date, articles, sections):
    value = {
        "requiredEdition": target_date,
        "articles": sorted((story_material(row) for row in articles), key=lambda row: str(row.get("id"))),
        "ownership": sorted(
            ({"slug": row.get("slug"), "articleIds": sorted(row.get("articleIds") or [])} for row in sections),
            key=lambda row: str(row.get("slug")),
        ),
    }
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def inspect_daily_dependency(*, now, desk, live, builder, integrity_state, integrity_detail):
    """Reuse real builder's selection rules even while prerequisites are missing.

    builder.build(now=now) is read-only (it never calls its --write CLI path).
    A partial selection fingerprint lets an existing failed budget be latched
    before upstream repair, without relying on a synthetic date marker.
    """
    target, reference, _ = builder.required_daily_target(now.astimezone(HKT))
    selected, sections, seen = [], [], set()
    material_pool, selected_material = set(), set()
    desks = desk.get("desks") if isinstance(desk.get("desks"), dict) else {}
    for slug in builder.DESK_ORDER:
        rows = desks.get(slug) if isinstance(desks.get(slug), list) else []
        # Include the entire current canonical reservoir, not only the top two
        # selected stories. Later clock-based promotion of an existing row is
        # therefore recognizable as old material. Unready evidence is never
        # admitted to an epoch's pool by daily_budget.
        material_pool.update(material_hash(row, slug) for row in rows if isinstance(row, dict))
        candidates = [row for row in rows if isinstance(row, dict) and builder.current_story(row, slug, reference)]
        candidates.sort(key=lambda row: builder.story_stamp(row, reference), reverse=True)
        picked = []
        for row in candidates:
            sid = str(row.get("id") or "").strip()
            if not sid or sid in seen:
                continue
            copied, error = builder.daily_candidate(row)
            if copied is None:
                continue
            seen.add(sid)
            picked.append(copied)
            selected_material.add(material_hash(copied, slug))
            if len(picked) == 2:
                break
        if picked:
            selected.extend(picked)
            sections.append({"slug": slug, "articleIds": [row["id"] for row in picked]})
    evidence = {
        "requiredEdition": target,
        "inputKey": input_fingerprint(target, selected, sections),
        "selectedArticleIds": sorted(row["id"] for row in selected),
        "selectedCount": len(selected),
        "materialPoolHashes": sorted(material_pool),
        "selectedMaterialHashes": sorted(selected_material),
        "ready": False,
        "reason": None,
        "readOnlyPreflight": True,
    }
    live_at = parse_time(live.get("lastUpdated"))
    coverage = live.get("coverage") if isinstance(live.get("coverage"), dict) else {}
    verified_at = parse_time(coverage.get("verifiedDraftCreatedAt"))
    coverage_ok = (
        isinstance(coverage, dict) and coverage.get("status") == "COMPLETE"
        and all(coverage.get(key) is True for key in ("sourceGateMet", "copyGateMet", "routingGateMet", "publishingGateMet"))
        and bool(str(coverage.get("verifiedDraftId") or "").strip())
    )
    if integrity_state != "CURRENT" or integrity_detail.get("depthMet") is not True:
        evidence["reason"] = "await-current-hard-depth-complete-desk"
    elif live_at is None or live_at > now or live_at.astimezone(HKT).date().isoformat() < target:
        evidence["reason"] = "await-genuine-current-live"
    # The canonical producer can legitimately target a missed Live slot nine
    # minutes before draft completion. That slot is not the verification clock.
    # Require the actual strict draft verification to have completed by this
    # observation, while retaining current-edition, source/copy and Desk gates.
    elif not coverage_ok or verified_at is None or verified_at > now or verified_at.astimezone(HKT).date().isoformat() < target:
        evidence["reason"] = "await-current-verified-live-source"
    else:
        try:
            daily, meta = builder.build(now=now)
            if meta.get("changed") is not True:
                evidence["reason"] = "daily-already-current-or-no-recovery-input"
            elif len(daily.get("articles") or []) < 8:
                evidence["reason"] = "await-eight-daily-safe-current-stories"
            elif input_fingerprint(target, daily["articles"], daily["sections"]) != evidence["inputKey"]:
                evidence["reason"] = "preflight-selection-not-consistent-with-canonical-builder"
            else:
                evidence["ready"] = True
                evidence["reason"] = "canonical-readonly-builder-input-verified"
        except (SystemExit, Exception) as exc:
            evidence["reason"] = "canonical-builder-rejected-input"
            evidence["detail"] = str(exc)
    return evidence


def audit_assignment(row):
    """Flat audit only: never recursively embed previousOutcome/outcomeBefore."""
    before = row.get("outcomeBefore") or {}
    return {
        "assignmentId": row.get("assignmentId"), "attempt": row.get("attempt"),
        "status": row.get("status"), "mode": row.get("mode"),
        "priorLatestDate": before.get("latestDate"),
        "priorDeskGeneratedAt": before.get("deskGeneratedAt"),
        "priorLiveLastUpdated": before.get("liveLastUpdated"),
    }


def public_daily_evidence(evidence):
    # The immutable epoch already retains the full clock-independent material
    # pool. Avoid duplicating thousands of hashes in snapshot/last-evidence
    # telemetry, without truncating the authoritative membership ledger.
    value = {key: item for key, item in evidence.items() if key != "materialPoolHashes"}
    value["materialPoolCount"] = len(evidence.get("materialPoolHashes") or [])
    return value


def daily_budget(previous, evidence):
    """Retain each material input epoch across held/blocked/unassigned cycles.

    Consume only confirmed dispatches once. A genuine READY new material input
    creates a new bounded epoch; an unready input never erases the active one.
    Old telemetry is imported conservatively at its prior reported attempt.
    """
    prior_state = previous.get("dailyRecoveryInput") or {}
    state = json.loads(json.dumps(prior_state)) if isinstance(prior_state, dict) else {}
    state.setdefault("epochs", [])
    state.setdefault("legacyAssignmentAudit", [])
    rows = [row for row in (previous.get("assignments") or []) if isinstance(row, dict) and row.get("robot") == "daily-recovery"]
    prior_row = rows[-1] if rows else None
    active = next((epoch for epoch in state["epochs"] if epoch["inputKey"] == state.get("activeInputKey")), None)
    if active is None:
        active = {"inputKey": evidence["inputKey"], "requiredEdition": evidence["requiredEdition"],
                  "dispatchesUsed": 0, "executionIds": [],
                  "materialPoolHashes": list(evidence["materialPoolHashes"]),
                  "materialPoolObserved": True}
        if prior_row:
            used = max(1, int(prior_row.get("attempt") or 1))
            active["dispatchesUsed"] = min(MAX_ATTEMPTS, used)
            state["legacyAssignmentAudit"].append(audit_assignment(prior_row))
            active["legacyImported"] = True
        state["epochs"].append(active)
        state["activeInputKey"] = active["inputKey"]
    if prior_row and prior_row.get("dailyInputKey") == active["inputKey"]:
        assignment_id = prior_row.get("assignmentId")
        confirmed = any(
            isinstance(item, dict) and item.get("robot") == "daily-recovery"
            and item.get("assignmentId") == assignment_id and item.get("dispatched") is True
            for item in (previous.get("execution") or [])
        )
        if confirmed and assignment_id not in active["executionIds"]:
            active["dispatchesUsed"] = min(MAX_ATTEMPTS, active["dispatchesUsed"] + 1)
            active["executionIds"].append(assignment_id)
    if evidence["ready"]:
        if evidence["inputKey"] != active["inputKey"]:
            known = next((epoch for epoch in state["epochs"] if epoch["inputKey"] == evidence["inputKey"]), None)
            admitted_material = {
                digest for epoch in state["epochs"]
                if epoch.get("requiredEdition") == evidence["requiredEdition"]
                and (epoch.get("materialPoolAdmitted") is True or epoch.get("materialPoolObserved") is True)
                for digest in (epoch.get("materialPoolHashes") or [])
            }
            new_selected_material = set(evidence["selectedMaterialHashes"]) - admitted_material
            new_edition = evidence["requiredEdition"] != active["requiredEdition"]
            if known is not None:
                # Reappearing old inputs retain their original spent budget.
                active = known
            elif new_edition or new_selected_material:
                active = {"inputKey": evidence["inputKey"], "requiredEdition": evidence["requiredEdition"], "dispatchesUsed": 0, "executionIds": []}
                state["epochs"].append(active)
            # Otherwise retain the active epoch and its attempts: a clock-only
            # reorder, removal or ID rename cannot manufacture new material.
            state["activeInputKey"] = active["inputKey"]
        if evidence["inputKey"] == active["inputKey"] and active.get("materialPoolAdmitted") is not True:
            active["materialPoolHashes"] = list(evidence["materialPoolHashes"])
            active["selectedMaterialHashes"] = list(evidence["selectedMaterialHashes"])
            active["materialPoolAdmitted"] = True
    state["lastInputEvidence"] = public_daily_evidence(evidence)
    state["maxAttemptsPerInput"] = MAX_ATTEMPTS
    if not evidence["ready"]:
        decision = {"status": "awaiting-daily-prerequisite", "dispatchable": False, "reason": evidence["reason"]}
    elif active["dispatchesUsed"] >= MAX_ATTEMPTS:
        decision = {"status": "stuck", "dispatchable": False, "requiresEditorReplan": True, "reason": "same-validated-daily-input-budget-exhausted"}
    else:
        decision = {"status": "assigned", "dispatchable": True, "reason": "validated-current-daily-input"}
    decision.update(dailyInputKey=active["inputKey"], attempt=min(MAX_ATTEMPTS, active["dispatchesUsed"] + 1))
    return state, decision
