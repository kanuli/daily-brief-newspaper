"""Read-only publisher recovery capability of the EIC's existing public-probe Robot."""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

if __package__:
    from .verified_draft_pending import DRAFT_ID, pending_verified_draft, stamp
else:
    from verified_draft_pending import DRAFT_ID, pending_verified_draft, stamp


OWNER = "Editor-in-Chief"
BRANCH = "cantonese_newspaper"
ROBOT = "public-probe"
REPOSITORY = "kanuli/daily-brief-newspaper"
DISPATCHER = "editor-in-chief-newsroom-assignment.yml"
WORKFLOWS = ("rolling-news-search.yml", "general-news-producer.yml",
             "live-publication-maintenance.yml", "editor-in-chief-maintenance.yml",
             "daily-today-recovery.yml", "pages-probe.yml",
             "merge-live-into-desk.yml", "pages.yml")
CATALOGUE = Path(__file__).resolve().parents[1] / "config/publisher-recovery-catalogue.json"
SHA = re.compile(r"[0-9a-f]{40}")
TASK_LIFETIME = timedelta(minutes=12)
MAX_BYTES = 8 * 1024 * 1024


def scheduled_assessment(data):
    if __package__:
        from .scheduled_service_observation_v13 import assess
    else:
        from scheduled_service_observation_v13 import assess
    return assess(data)


def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def read(path):
    with Path(path).open("rb") as stream:
        value = stream.read(MAX_BYTES + 1)
    if len(value) > MAX_BYTES:
        raise ValueError("RECOVERY_INPUT_SIZE_HOLD")
    return json.loads(value)


def require_eic_run(env):
    expected = f"{REPOSITORY}/.github/workflows/{DISPATCHER}@refs/heads/main"
    if (env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REPOSITORY") != REPOSITORY
            or env.get("GITHUB_WORKFLOW_REF") != expected or env.get("GITHUB_REF") != "refs/heads/main"
            or env.get("EIC_RECOVERY_OPERATION") != "public-probe:publisherRecovery:READ_ONLY"
            or not re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ID", ""))
            or not re.fullmatch(r"[1-9][0-9]*", env.get("GITHUB_RUN_ATTEMPT", "1"))):
        raise ValueError("EIC_RUN_SCOPE_HOLD")


def authorize(registry, cycle, now):
    ctl = registry.get("controlPlane") or {}
    probe = next((r for r in registry.get("robots", []) if r.get("id") == ROBOT), {})
    checked = stamp(cycle.get("checkedAt"))
    if (cycle.get("role") != OWNER or cycle.get("dispatcher") != DISPATCHER
            or ctl.get("dispatcherWorkflow") != DISPATCHER
            or probe.get("readOnlyObservation") is not True
            or probe.get("capabilities", {}).get("publisherRecovery") !=
                {"branch": BRANCH, "owner": OWNER, "catalogueVersion": 1, "scope": "READ_ONLY", "mode": "EIC_INLINE"}
            or not isinstance(cycle.get("assignments"), list)
            or checked is None or not timedelta(0) <= now - checked <= TASK_LIFETIME):
        raise ValueError("EIC_ASSIGNMENT_SCOPE_HOLD")


def evidence_code(cycle, draft, live, pages, now):
    snap = cycle.get("evidenceSnapshot") or {}
    rows = [r for r in cycle["assignments"] if isinstance(r, dict)]
    codes = set()
    if draft.get("status") == "VERIFIED_DRAFT":
        created, target = stamp(draft.get("createdAt")), stamp(draft.get("targetPublication"))
        if not isinstance(draft.get("draftId"), str) or not DRAFT_ID.fullmatch(draft["draftId"]):
            codes.add("DRAFT_ID_INVALID")
        if created is None or target is None or created > now:
            codes.add("DRAFT_TIMESTAMP_INVALID")
        elif not pending_verified_draft(draft, now, live):
            articles = draft.get("articles")
            stamps = [stamp(a.get("publishedAt")) if isinstance(a, dict) else None
                      for a in articles] if isinstance(articles, list) else []
            if not stamps or any(t is None or not timedelta(0) <= now-t <= timedelta(days=1) for t in stamps):
                codes.add("ARTICLE_EVIDENCE_EXPIRED_OR_INVALID")
            elif target > created:
                codes.add("DRAFT_TARGET_OUTSIDE_APPROVED_SLOT")
            else:
                codes.add("DRAFT_EXPIRED_OR_SUPERSEDED")
    if snap.get("externalPublisherSlotCurrent") is False or any(
            row.get("requiresExternalPublisher") is True for row in rows):
        codes.add("EXTERNAL_PUBLISHER_RECEIPT_REQUIRED")
    if any(row.get("robot") == "live-publisher" and row.get("dispatchable") is not True for row in rows):
        codes.add("LOCAL_PUBLISHER_DISPATCH_BLOCKED")
    if any(row.get("robot") == "live-publisher" and row.get("dispatchable") is True for row in rows):
        codes.add("LOCAL_PUBLISHER_EXECUTION_RECEIPT_PENDING")
    if any(row.get("robot") == "daily-recovery" and not row.get("dispatchable") for row in rows):
        codes.add("DAILY_AWAITS_CURRENT_LIVE")
    if snap.get("staleDesks"):
        codes.add("DESK_STALE")
    if snap.get("publicationValidatorOk") is False:
        codes.add("EDITORIAL_PUBLICATION_VALIDATION_FAILED")
    currentness = pages.get("publicationCurrentness") or {}
    if pages.get("match") is True and currentness.get("current") is not True:
        codes.add("PUBLIC_PARITY_WITHOUT_CURRENTNESS")
    if not codes and not cycle.get("healthy") and rows:
        codes.add("UNKNOWN_PUBLICATION_FAILURE")
    return codes


def get_json(endpoint):
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + endpoint,
                                     headers={"Accept": "application/vnd.github+json",
                                              "User-Agent": "EIC-Publisher-Recovery"})
    # Public GitHub metadata only. Never forward the dispatcher credential.
    with urllib.request.urlopen(request, timeout=3) as response:
        raw = response.read(768 * 1024 + 1)
    if len(raw) > 768 * 1024:
        raise ValueError("JOB_METADATA_SIZE_HOLD")
    return json.loads(raw)


def scan(expected_probe=None, expected_publisher=None):
    """Bounded GETs against registered repository paths; external executor is a separate interface."""
    out = {}
    for workflow in WORKFLOWS:
        try:
            expected = (expected_probe if workflow == "pages-probe.yml" else
                        expected_publisher if workflow == "live-publication-maintenance.yml" else None)
            if expected is not None:
                rid, attempt = expected
                if not all(type(value) is int and value > 0 for value in expected):
                    raise ValueError("JOB_PROVENANCE_HOLD")
                r = get_json(f"/actions/runs/{rid}/attempts/{attempt}")
                if r.get("id") != rid or r.get("run_attempt") != attempt or r.get("path") != ".github/workflows/" + workflow:
                    raise ValueError("JOB_PROVENANCE_HOLD")
                candidates = [r]
            else:
                candidates = get_json("/actions/workflows/" + workflow + "/runs?branch=main&per_page=1")["workflow_runs"]
            if not candidates:
                out[workflow] = {"status": "NO_RUN_FOUND"}
                continue
            row = candidates[0]
            rid, attempt = row.get("id"), row.get("run_attempt")
            if type(rid) is not int or type(attempt) is not int or row.get("head_branch") != "main":
                raise ValueError("JOB_PROVENANCE_HOLD")
            if not SHA.fullmatch(str(row.get("head_sha", ""))):
                raise ValueError("JOB_PROVENANCE_HOLD")
            job_page = get_json(f"/actions/runs/{rid}/attempts/{attempt}/jobs?per_page=20")
            jobs = job_page["jobs"]
            if job_page.get("total_count") != len(jobs) or not jobs:
                raise ValueError("JOB_METADATA_INCOMPLETE_HOLD")
            if any(j.get("run_id") != rid or j.get("head_sha") != row["head_sha"]
                   or j.get("run_attempt", attempt) != attempt for j in jobs):
                raise ValueError("JOB_PROVENANCE_HOLD")
            primary = {k: row.get(k) for k in ("id", "run_attempt", "head_sha", "status", "conclusion",
                                               "created_at", "updated_at")}
            primary["jobs"] = [{"id": j.get("id"), "started_at": j.get("started_at"),
                                "completed_at": j.get("completed_at"), "conclusion": j.get("conclusion"),
                                "failed_steps": [s["name"][:100] for s in j.get("steps", [])
                                                 if s.get("conclusion") == "failure"][:8]}
                               for j in jobs]
            primary["receipt_sha256"] = digest(primary)
            out[workflow] = primary
        except (OSError, KeyError, ValueError, TypeError):
            out[workflow] = {"status": "RECEIPT_NOT_VERIFIED"}
    return out


def classify_runs(codes, runs, now):
    producer = runs.get("general-news-producer.yml") or {}
    publisher = runs.get("live-publication-maintenance.yml") or {}
    editor = runs.get("editor-in-chief-maintenance.yml") or {}
    for row, label in ((producer, "PRODUCER"), (publisher, "FALLBACK_PUBLISHER"), (editor, "EDITOR"),
                       (runs.get("merge-live-into-desk.yml") or {}, "ROLLING_DESK"),
                       (runs.get("daily-today-recovery.yml") or {}, "DAILY"),
                       (runs.get("pages.yml") or {}, "PAGES_DEPLOYMENT")):
        when = stamp(row.get("updated_at"))
        if when is None or not timedelta(0) <= now-when <= timedelta(days=1):
            continue
        if row.get("conclusion") in {"failure", "timed_out", "cancelled"}:
            codes.add(label + "_EXECUTION_" + row["conclusion"].upper())
        started = stamp(row.get("created_at"))
        if row.get("status") in {"queued", "in_progress"} and started and now-started > TASK_LIFETIME:
            codes.add(label + "_EXECUTION_STALLED")
        if label == "PRODUCER" and any(
                "verified source" in step.lower() or "verification/copy" in step.lower()
                for job in row.get("jobs", []) for step in job.get("failed_steps", [])):
            codes.add("PRODUCER_SOURCE_OR_COPY_STAGE_FAILED")
    if not publisher.get("id"):
        codes.add("FALLBACK_PUBLISHER_RUN_NOT_ESTABLISHED")



def publisher_receipt(runs, cycle):
    row = runs.get("live-publication-maintenance.yml") or {}
    expected = next((entry for entry in cycle.get("execution", [])
                     if isinstance(entry, dict) and entry.get("robot") == "live-publisher"), {})
    if not row.get("id"):
        return "FALLBACK_RECEIPT_MISSING"
    if not expected.get("runId"):
        return "FALLBACK_RUN_UNBOUND_TO_ASSIGNMENT"
    if (expected["runId"] != row["id"] or expected.get("headSha") != row.get("head_sha")
            or type(expected.get("runAttempt")) is not int
            or expected["runAttempt"] != row.get("run_attempt")
            or not row.get("receipt_sha256")):
        return "FALLBACK_RECEIPT_CONTRADICTION"
    return "FALLBACK_RECEIPT_CORRELATED"

def publication_candidate(cycle, live, desk, pages, repo_sha, now):
    checked = stamp(pages.get("checkedAt"))
    current = pages.get("publicationCurrentness") or {}
    live_at = stamp(live.get("lastUpdated"))
    public_at = stamp(pages.get("observedLiveAt"))
    return bool(SHA.fullmatch(repo_sha) and pages.get("sourceCommit") == repo_sha
                and checked and timedelta(0) <= now-checked <= TASK_LIFETIME
                and live_at and live_at <= checked and public_at == live_at
                and stamp(desk.get("generatedAt")) == live_at
                and stamp(pages.get("observedDeskAt")) == live_at
                and current.get("current") is True
                and pages.get("publicationRecoveryVerified") is True
                and pages.get("liveMatch") is True and pages.get("deskMatch") is True
                and pages.get("dailyMatch") is True and pages.get("publicationComplete") is True
                and pages.get("match") is True
                and (cycle.get("evidenceSnapshot") or {}).get("publicationValidatorOk") is True)


def execute(registry, catalogue, cycle, draft, live, desk, pages, previous, repo_sha, *,
            now, receipt_reader=None, execution_id=None, scheduled=None):
    authorize(registry, cycle, now)
    if (catalogue.get("version"), catalogue.get("branch"), catalogue.get("owner"), catalogue.get("robot")) != (1, BRANCH, OWNER, ROBOT):
        raise ValueError("RECOVERY_CATALOGUE_SCOPE_HOLD")
    codes = evidence_code(cycle, draft, live, pages, now)
    from desk_freshness_policy import current_daily_dates
    from scheduled_publication_contract import desk_checkpoint_errors, is_scheduled, publisher_errors
    schema_errors, checkpoint_errors = [], []
    if is_scheduled(live):
        schema_errors = publisher_errors(live, now=now)
        if not schema_errors and live.get("date") not in current_daily_dates(now=now):
            schema_errors.append("Live edition is outside the current HKT date window")
        if schema_errors:
            codes.add("SCHEDULED_LIVE_CONTRACT_REJECTED")
        else:
            checkpoint_errors = desk_checkpoint_errors(live, desk, now=now)
            if checkpoint_errors:
                codes.add("SCHEDULED_LIVE_DESK_CHECKPOINT_REJECTED")
        if (pages.get("publicationCurrentness") or {}).get("dailyCurrent") is False:
            codes.add("SCHEDULED_DAILY_NOT_CURRENT")
        if pages.get("liveMatch") is False or pages.get("deskMatch") is False:
            codes.add("SCHEDULED_PUBLIC_PAGES_CONTENT_MISMATCH")
        if pages.get("sourceCommit") and pages["sourceCommit"] != repo_sha:
            codes.add("SCHEDULED_PAGES_SOURCE_COMMIT_MISMATCH")
    scheduled_result = None
    if scheduled is not None:
        if scheduled.get("task_id") != "6a8690a77d608191ae9a860ff3435f92":
            raise ValueError("RECOVERY_SCHEDULED_BRANCH_HOLD")
        scheduled_result = scheduled_assessment(scheduled)
        codes.update(scheduled_result["reason_codes"])
        when = stamp(scheduled.get("checked_at"))
        if when is None or not timedelta(0) <= now - when <= TASK_LIFETIME:
            codes.add("SCHEDULED_OBSERVATION_STALE_OR_FUTURE_HOLD")
    if not SHA.fullmatch(repo_sha):
        raise ValueError("EIC_CHECKOUT_COMMIT_REQUIRED")
    old = previous.get("publisherRecoveryRobot") or {}
    if old.get("reasonCodes") == ["RECOVERY_EXECUTION_INTERRUPTED_OR_MISSING"]:
        old = old.get("resumeFrom") or {}
    journal = previous.get("publisherRecoveryAudit") or []
    open_issue = old.get("outcome") in {"HOLD", "CURRENT_PUBLICATION_EVIDENCE_FOR_EIC_REVIEW"}
    if not codes and not open_issue:
        return {"outcome": "NO_ASSIGNMENT", "robot": ROBOT, "catalogueVersion": 1, "NO_SEND": True}
    incident = old.get("incidentId")
    if not incident or (codes and old.get("outcome") == "CURRENT_PUBLICATION_EVIDENCE_FOR_EIC_REVIEW"):
        incident = "canto-publisher-" + digest({"cycle": cycle["cycleId"], "faults": sorted(codes)})[:24]
    if (not isinstance(incident, str) or not re.fullmatch(r"canto-publisher-[0-9a-f]{24}", incident)):
        raise ValueError("RECOVERY_INCIDENT_SCOPE_HOLD")
    same_incident = old.get("incidentId") == incident
    # Bind scheduled diagnostics to the actual content, including same-slot corrections.
    scheduled_content = [digest(live), digest(desk)] if is_scheduled(live) else []
    # A replayed EIC snapshot must never consume a fresh network attempt after restart.
    input_binding = digest({"incident": incident, "faults": sorted(codes), "draft": digest(draft),
                            "live": live.get("lastUpdated"), "desk": desk.get("generatedAt"),
                            "scheduledContent": scheduled_content, "scheduled": {k:v for k,v in (scheduled or {}).items() if k != "checked_at"}, "source": repo_sha, "probe": [pages.get("probeRunId"), pages.get("probeRunAttempt")]})
    prior = next((r for r in (old, *reversed(journal[-32:]))
                  if r.get("inputBinding") == input_binding), None)
    if prior is not None:
        # Reassess HOLD after cooldown if the provider may have finished the same probe.
        checked = stamp(prior.get("checkedAt"))
        if checked is None or now < checked:
            raise ValueError("RECOVERY_CLOCK_ROLLBACK_HOLD")
        prior_proc = (catalogue.get("actions") or {}).get(prior.get("performed"), {})
        cooldown = timedelta(minutes=prior_proc.get("cooldown_minutes", 15))
        if (prior.get("outcome") != "HOLD" or prior.get("assignmentCycle") == cycle["cycleId"]
                or now - checked < cooldown or (prior.get("attempt", 1) >= catalogue.get("max_attempts_per_evidence_binding", 1))):
            return prior
    # Promotion to review requires repository- and commit-bound provider metadata.
    checks_publication = not codes and publication_candidate(cycle, live, desk, pages, repo_sha, now)
    if old.get("reviewState") == "CTO_INDEPENDENT_REVIEW_REQUIRED" and not codes:
        return old  # Only independent CTO evidence can advance this state.
    runs = receipt_reader() if checks_publication and receipt_reader else {}
    probe_run = runs.get("pages-probe.yml") or {}
    verified = bool(checks_publication and type(pages.get("probeRunId")) is int and pages["probeRunId"] > 0
                    and type(pages.get("probeRunAttempt")) is int and pages["probeRunAttempt"] > 0
                    and probe_run.get("head_sha") == repo_sha
                    and probe_run.get("id") == pages.get("probeRunId")
                    and probe_run.get("run_attempt") == pages.get("probeRunAttempt")
                    and probe_run.get("conclusion") == "success"
                    and stamp(probe_run.get("created_at")) is not None
                    and stamp(probe_run.get("updated_at")) is not None
                    and stamp(probe_run["created_at"]) <= stamp(pages["checkedAt"]) <= stamp(probe_run["updated_at"])
                    and probe_run.get("receipt_sha256"))
    if not codes and not verified:
        codes.add("PUBLICATION_RECOVERY_EVIDENCE_REQUIRED")
    procedure = ("RECHECK_PUBLICATION" if verified else "RECHECK_RESERVED_DRAFT"
                 if any(c.startswith(("DRAFT_", "ARTICLE_")) for c in codes) else
                 "INSPECT_PUBLICATION_CONTRACT" if schema_errors or checkpoint_errors else
                 "RECONCILE_SCHEDULED_OUTCOME" if scheduled_result else "INSPECT_EXECUTION")
    action = catalogue["actions"][procedure]
    if action.get("scope") != "READ_ONLY" or action.get("budget") != 1:
        raise ValueError("RECOVERY_CATALOGUE_ACTION_HOLD")
    signature = digest({"version": 1, "procedure": procedure, "faults": sorted(codes),
                        "draft": digest(draft), "live": live.get("lastUpdated"), "desk": desk.get("generatedAt"),
                        "verified": verified, "scheduledContent": scheduled_content, "incident": incident, "attempt": (prior.get("attempt", 1) + 1 if prior else 1)})
    for row in (old, *journal[-32:]):
        if row.get("idempotencyKey") == signature:
            return row
    old_time = stamp(old.get("checkedAt"))
    if old_time and now < old_time:
        raise ValueError("RECOVERY_CLOCK_ROLLBACK_HOLD")
    if not verified and same_incident and old_time and now-old_time < timedelta(minutes=action["cooldown_minutes"]):
        return old  # The protected EIC cycle will reassess without retrying prematurely.
    needs_runs = procedure in {"INSPECT_EXECUTION", "INSPECT_PUBLICATION_CONTRACT"} or "EXTERNAL_PUBLISHER_RECEIPT_REQUIRED" in codes
    if needs_runs and not runs and receipt_reader:
        runs = receipt_reader()
    if runs:
        classify_runs(codes, runs, now)
    receipt_status = publisher_receipt(runs, cycle if cycle.get("execution") else previous)
    if receipt_status == "FALLBACK_RECEIPT_CONTRADICTION":
        codes.add(receipt_status)
        verified = False
    return {"schema": "EIC_PUBLISHER_RECOVERY_V1", "robot": ROBOT, "branch": BRANCH, "owner": OWNER,
            "catalogueVersion": 1, "catalogueSha256": digest(catalogue), "assignmentCycle": cycle["cycleId"],
            "checkedAt": now.isoformat(), "idempotencyKey": signature, "sourceCommit": repo_sha,
            "outcome": "CURRENT_PUBLICATION_EVIDENCE_FOR_EIC_REVIEW" if verified else "HOLD",
            "reasonCodes": sorted(codes), "performed": procedure,
            "incidentId": incident, "executionId": execution_id or signature,
            "attempt": prior.get("attempt", 1) + 1 if prior else 1,
            "inputBinding": input_binding, "workflowEvidence": runs, "scheduledPublisher": scheduled_result,
            "publicationContractErrors": schema_errors + checkpoint_errors,
            "rootCause": "NOT_VERIFIED", "externalPublisherReceipt": "NOT_VERIFIED",
            "publisherReceiptStatus": receipt_status,
            "publicationEvidenceSha256": digest(pages) if verified else None,
            "eicVerification": "REQUIRED", "ctoIndependentVerification": "REQUIRED",
            "reviewState": "EIC_REVIEW_REQUIRED" if verified else "HOLD",
            "nextAction": action["escalate"], "productionMutation": False, "NO_SEND": True}



def record_eic_review(record, cycle, now, execution_id):
    """Record the protected EIC cycle's actual validator decision for its exact result."""
    if (record.get("assignmentCycle") != cycle.get("cycleId")
            or record.get("executionId") != execution_id
            or record.get("reviewState") != "EIC_REVIEW_REQUIRED"):
        return record
    approved = ((cycle.get("evidenceSnapshot") or {}).get("publicationValidatorOk") is True
                and not cycle.get("publishedStaleDesks")
                and not cycle.get("externalPublisherNoProgress"))
    return {**record, "eicVerification": {
        "owner": OWNER, "cycle": cycle["cycleId"], "executionId": execution_id,
        "checkedAt": now.isoformat(), "result": "ACCEPT_EVIDENCE" if approved else "HOLD",
        "evidenceSha256": record["publicationEvidenceSha256"]},
        "reviewState": "CTO_INDEPENDENT_REVIEW_REQUIRED" if approved else "HOLD"}

def merge_recovery_telemetry(cycle, previous, record, step_outcome):
    """Preserve the prior audit, but never label an interrupted operation successful."""
    audit = list(previous.get("publisherRecoveryAudit") or [])
    prior = previous.get("publisherRecoveryRobot") or {}
    if step_outcome != "success" or not isinstance(record, dict) or not record.get("outcome"):
        key = digest({"cycle": cycle.get("cycleId"), "step": step_outcome, "prior": prior.get("resumeFrom", prior).get("idempotencyKey")})
        record = {"schema": "EIC_PUBLISHER_RECOVERY_V1", "robot": ROBOT, "branch": BRANCH,
                  "owner": OWNER, "assignmentCycle": cycle.get("cycleId"), "checkedAt": cycle.get("checkedAt"),
                  "incidentId": prior.get("incidentId"), "idempotencyKey": key,
                  "outcome": "HOLD", "reviewState": "HOLD",
                  "reasonCodes": ["RECOVERY_EXECUTION_INTERRUPTED_OR_MISSING"],
                  "previousExecutionId": prior.get("executionId"),
                  "resumeFrom": prior, "NO_SEND": True, "productionMutation": False,
                  "eicVerification": "REQUIRED", "ctoIndependentVerification": "REQUIRED",
                  "nextAction": "EIC retries bounded diagnosis; no production repair authorized"}
        # Do not recursively nest failure records on repeated interrupted cycles.
        record["resumeFrom"] = prior.get("resumeFrom", prior)
    elif record.get("outcome") == "NO_ASSIGNMENT":
        record = prior
    if record.get("idempotencyKey") and not any(x.get("idempotencyKey") == record["idempotencyKey"] for x in audit):
        audit.append(record)
    cycle.update(publisherRecoveryAudit=audit[-32:], publisherRecoveryRobot=record,
                 publisherRecoveryExecution=step_outcome or "not-run")
    return cycle


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("registry", "cycle", "draft", "live", "desk", "pages", "previous", "output"):
        p.add_argument("--" + arg, type=Path, required=True)
    p.add_argument("--scheduled", type=Path, help="Read-only reviewed normalized task evidence, never a scheduler credential")
    args = p.parse_args()
    require_eic_run(os.environ)
    sha = os.environ.get("EIC_SOURCE_COMMIT", "")
    if not SHA.fullmatch(sha):
        raise ValueError("EIC_CHECKOUT_COMMIT_REQUIRED")
    names = ("registry", "cycle", "draft", "live", "desk", "pages", "previous")
    data = {name: read(getattr(args, name)) for name in names}
    pages = data["pages"]
    probe = (pages.get("probeRunId"), pages.get("probeRunAttempt"))
    if not all(type(x) is int and x > 0 for x in probe):
        probe = None
    publisher = next((row for row in data["previous"].get("execution", [])
                      if isinstance(row, dict) and row.get("robot") == "live-publisher"
                      and row.get("runId")), {})
    expected_publisher = (publisher.get("runId"), publisher.get("runAttempt")) if publisher else None
    from scheduled_service_observation_v13 import PUBLISHER, unavailable
    scheduled = (read(args.scheduled) if args.scheduled else
                 data["previous"].get("scheduledPublisherObservation",
                                      unavailable(PUBLISHER, data["cycle"]["checkedAt"])))
    result = execute(catalogue=read(CATALOGUE), repo_sha=sha, scheduled=scheduled,
                     now=datetime.now(timezone.utc), receipt_reader=lambda: scan(probe, expected_publisher),
                     execution_id="github:" + os.environ["GITHUB_RUN_ID"] + ":" +
                         os.environ.get("GITHUB_RUN_ATTEMPT", "1"), **data)
    result = record_eic_review(result, data["cycle"], datetime.now(timezone.utc),
                               "github:" + os.environ["GITHUB_RUN_ID"] + ":" +
                               os.environ.get("GITHUB_RUN_ATTEMPT", "1"))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")


if __name__ == "__main__":
    main()
