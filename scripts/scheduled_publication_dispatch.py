"""Gate existing EIC workflow dispatches on the checked-out publication evidence."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

from atomic_publish import atomic_write_json
from desk_freshness_policy import current_daily_dates
from scheduled_publication_contract import (
    daily_payload_error, desk_checkpoint_errors, is_scheduled, publisher_errors, stamp,
)

SCHEMA = "EIC_SCHEDULED_PUBLICATION_DISPATCH_V1"
DEPENDENTS = {"desk-merge", "daily-recovery", "pages"}
DISPATCH_COOLDOWN = timedelta(minutes=15)


def evidence_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":")).encode()).hexdigest()


def recent_dispatches(previous, bindings, now):
    """Use the EIC's existing recorded dispatched=true result, never a plan alone."""
    prior = (previous or {}).get("scheduledPublicationDispatch") or {}
    if prior.get("schema") != SCHEMA:
        return {}
    caught = dict(prior.get("recentDispatches") or {})
    submitted = prior.get("eligibleDispatches") or {}
    for execution in (previous or {}).get("execution", []):
        name = execution.get("robot")
        entry = submitted.get(name)
        if (entry and execution.get("dispatched") is True
                and execution.get("assignmentId") == entry["assignmentId"]
                and execution.get("workflow") == entry["workflow"]):
            caught[name] = {**entry, "checkedAt": prior.get("checkedAt")}
    valid = {}
    for name, entry in caught.items():
        if name not in bindings or entry.get("evidenceSha256") != bindings[name]:
            continue
        try:
            if timedelta(0) <= now - stamp(entry["checkedAt"]) < DISPATCH_COOLDOWN:
                valid[name] = entry
        except (KeyError, TypeError, ValueError):
            continue
    return valid



def gate(plan, live, desk, daily, *, now=None, previous=None):
    """Apply HOLD to dependent assignments only. Never grant dispatch permission."""
    if not is_scheduled(live):
        return None
    now = now or datetime.now(timezone.utc)
    dates = current_daily_dates(now=now)
    errors = publisher_errors(live, now=now)
    if not errors and live.get("date") not in dates:
        errors.append("Live edition is outside the current HKT date window")
    checkpoint = [] if errors else desk_checkpoint_errors(live, desk, now=now)
    daily_date = daily.get("date") if isinstance(daily, dict) else None
    daily_date_current = isinstance(daily_date, str) and daily_date in dates
    daily_error = daily_payload_error(daily) if daily_date_current else None
    current_daily = daily_date_current and daily_error is None
    live_digest = evidence_digest(live)
    bindings = {"desk-merge": live_digest,
                "daily-recovery": evidence_digest([live_digest, desk]),
                "pages": evidence_digest([live_digest, desk, daily])}
    recent = recent_dispatches(previous, bindings, now)
    field_errors = []
    for error in errors:
        match = re.fullmatch(r"items\[([0-9]+)\]: (.+)", error)
        field_errors.append({"itemIndex": int(match[1]) if match else None,
                             "reason": match[2] if match else error})
    receipt = {"schema": SCHEMA, "checkedAt": now.isoformat(), "liveSha256": live_digest,
               "liveErrors": errors, "fieldErrors": field_errors, "checkpointErrors": checkpoint,
               "dailyCurrent": current_daily, "dailyError": daily_error, "held": [], "eligibleDispatches": {},
               "recentDispatches": recent}
    if errors:
        receipt["status"] = "LIVE_CONTRACT_HOLD"
    elif checkpoint:
        receipt["status"] = "WAIT_FOR_ROLLING_DESK"
    elif daily_error:
        receipt["status"] = "WAIT_FOR_VALID_DAILY"
    elif not current_daily:
        receipt["status"] = "WAIT_FOR_CURRENT_DAILY"
    else:
        receipt["status"] = "PASS"

    for row in plan.get("assignments", []):
        robot = row.get("robot")
        if robot not in DEPENDENTS or not row.get("dispatchable"):
            continue
        blockers = []
        if errors:
            blockers.append("scheduled-live-contract-hold")
        elif checkpoint and robot != "desk-merge":
            blockers.append("scheduled-live-desk-checkpoint-hold")
        elif not current_daily and robot == "pages":
            blockers.append("scheduled-current-daily-required")
        previous_dispatch = recent.get(robot)
        if (not blockers and previous_dispatch and row.get("workflow") == previous_dispatch["workflow"]
                and row.get("assignmentId")):
            blockers.append("scheduled-equivalent-dispatch-cooldown")
        if blockers:
            row["blockedBy"] = list(dict.fromkeys([*(row.get("blockedBy") or []), *blockers]))
            row["dispatchable"] = False
            row["status"] = "publication-contract-hold"
            receipt["held"].append(robot)
        elif row.get("assignmentId") and row.get("workflow"):
            receipt["eligibleDispatches"][robot] = {"assignmentId": row["assignmentId"],
                                                    "workflow": row["workflow"],
                                                    "evidenceSha256": bindings[robot]}
    plan["scheduledPublicationDispatch"] = receipt
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("plan", "live", "desk", "daily", "receipt"):
        parser.add_argument("--" + field, type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--previous", type=Path)
    opts = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", opts.commit):
        parser.error("expected the exact GitHub checkout commit")
    raw_live = opts.live.read_bytes()
    live = json.loads(raw_live)
    plan, desk, daily = [json.loads(path.read_bytes()) for path in (opts.plan, opts.desk, opts.daily)]
    previous = json.loads(opts.previous.read_bytes()) if opts.previous else None
    receipt = gate(plan, live, desk, daily, previous=previous)
    if receipt is None:
        return
    receipt["sourceCommit"] = opts.commit
    receipt["liveFileSha256"] = hashlib.sha256(raw_live).hexdigest()
    atomic_write_json(opts.receipt, receipt)
    atomic_write_json(opts.plan, plan)
    print("EIC_SCHEDULED_PUBLICATION_DISPATCH", receipt["status"], receipt["liveSha256"])


if __name__ == "__main__":
    main()
