"""Human-approved one-shot EIC proof repair: never news fetch/model/publication.

This is NOT a trial continuation or an extension of its expired execution TTL.
The original failed result stays immutable. Original work must have completed
inside that TTL; a separately approved audit checks existing output at REAL now.
"""
import argparse
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import urllib.request

import editorial_revision_trial as current
from verified_draft_pending import draft_has_locator_only_sources

REVISION = "929e6c34cb8ba78a4de0c4ba76957f281055866f788b28de6bc81ee27b3f492d"
ORIGINAL_ROOT = f"{current.TRIAL_ROOT}/{REVISION}"
AUDIT_ROOT = ORIGINAL_ROOT + ".human-approved-proof-audit"
APPROVED_AT = "2026-10-10T04:14:55Z"
APPROVAL_END = "2026-10-10T04:44:55Z"
CHILD = "38021801782"
HEAD = "d1ca7754367259e68d4b122b7ccc384b90a57848"
ORIGINAL_MODULE_BLOB = "bb931dbd104234af244c045d964b33c2a10b9267"
CLAIM_SHA = "16c1804f5e60e0101736c9f3f24c9938cdc56742"
BIND_SHA = "4dfdc22ee086708be85d5f8b480852ce8ecf91a6"
RESULT_SHA = "56f1420e72746984fc175020d38ebcc0b82c797a"
DRAFT_SHA = "0ce165ae632bca5508792098ff1e2017b8727431"
CAPACITY_SHA = "1c6e90f6ed820cd591feb752f689798881bd4dff"
PUBLISHED_COMMIT = "234fa0eec208540c19916e4dade8467a7e758490"
PUBLISHED_LIVE_SHA = "e4f8a8dee10cebb176f366a335fb992caa87c0d9"
PUBLISH_RUN = "38023175355"
PUBLISH_HEAD = "99b22549b7a620a4bdb243cf25f35c792419690e"
FINALIZER = "Finalize reviewed trial from exact persisted draft or preserve failed capacity"


class AuditStore(current.TrialStore):
    @staticmethod
    def allowed_path(path):
        return path in {AUDIT_ROOT + ".claim.json", AUDIT_ROOT + ".result.json"} or current.TrialStore.allowed_path(path)

    def published_live(self):
        req = urllib.request.Request(
            f"https://api.github.com/repos/{current.REPOSITORY}/contents/data/live.json?ref={PUBLISHED_COMMIT}",
            headers=self.headers(), method="GET")
        raw = self.json_request(req)
        if not raw or raw.get("encoding") != "base64":
            raise current.ProbeFailure("proof-audit", "published-live-unavailable")
        return {"sha": raw["sha"], "value": json.loads(base64.b64decode(raw["content"]))}


def read_action(store, run, suffix=""):
    req = urllib.request.Request(
        f"https://api.github.com/repos/{current.REPOSITORY}/actions/runs/{run}{suffix}",
        headers=store.headers(), method="GET")
    return store.json_request(req)


def require(value, reason):
    if not value:
        raise current.ProbeFailure("proof-audit", reason)


def prove(root, original, store, now, records, draft, capacity):
    require([row and row.get("sha") for row in records] == [CLAIM_SHA, BIND_SHA, RESULT_SHA], "immutable-evidence-changed")
    claim, binding, failure = [row["value"] for row in records]
    require(draft and draft["sha"] == DRAFT_SHA and capacity and capacity["sha"] == CAPACITY_SHA
            and capacity["value"] == claim.get("priorCapacity"), "draft-or-failed-capacity-changed")
    require(original.CONTRACT_REVISION == REVISION and claim.get("contract") == original.CONTRACT
            and claim.get("reviewedSources") == original.REVIEWED_SOURCES
            and binding.get("reviewedSources") == original.REVIEWED_SOURCES
            and original.reviewed_code(root), "original-reviewed-code-not-established")
    raw = (root / "scripts/editorial_revision_trial.py").read_bytes()
    require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == ORIGINAL_MODULE_BLOB,
            "original-validator-module-changed")
    require(failure.get("status") == "EDITORIAL_TRIAL_FAILED"
            and failure.get("failureCode") == "claim-child-code-binding-failed"
            and failure.get("editorialOutcomeVerified") is False
            and failure.get("publicationPermissionGranted") is False
            and failure.get("remainingAttempts") == 0 and failure.get("childRunId") == CHILD
            and binding.get("childRunId") == CHILD and binding.get("dispatcherRunId") == claim.get("dispatcherRunId")
            and claim.get("remainingAttempts") == 0 and claim.get("publicationPermissionGranted") is False,
            "not-exact-spent-cache-only-failure")
    start = current.parse_stamp(claim["claimedAt"], "proof-audit")
    expiry = current.parse_stamp(claim["expiresAt"], "proof-audit")
    bound = current.parse_stamp(binding["boundAt"], "proof-audit")
    created = current.checked_clock(draft["value"].get("createdAt"), now)
    require(expiry - start == timedelta(minutes=20) and start <= bound <= created <= expiry <= now,
            "original-work-outside-original-window")
    run = read_action(store, CHILD)
    require(run and str(run.get("id")) == CHILD and run.get("head_sha") == HEAD
            and type(run.get("run_attempt")) is int and run["run_attempt"] == 1
            and run.get("event") == "workflow_dispatch" and run.get("head_branch") == "main"
            and run.get("repository", {}).get("full_name") == current.REPOSITORY
            and run.get("name") == "General News Verified Producer"
            and run.get("path") == ".github/workflows/general-news-producer.yml"
            and run.get("status") == "completed" and run.get("conclusion") == "failure"
            and bound <= current.parse_stamp(run.get("updated_at"), "proof-audit") <= expiry,
            "exact-child-completion-not-proven")
    jobs = read_action(store, CHILD, "/jobs?per_page=100").get("jobs") or []
    produce = [row for row in jobs if row.get("id") == 114125192569]
    require(len(produce) == 1, "exact-produce-job-missing")
    job = produce[0]; steps = job.get("steps") or []
    require(job.get("name") == "produce" and job.get("run_id") == int(CHILD)
            and job.get("status") == "completed" and job.get("conclusion") == "failure"
            and [row["name"] for row in steps if row.get("conclusion") == "failure"] == [FINALIZER]
            and all(any(row.get("name") == name and row.get("conclusion") == "success" for row in steps)
                    for name in ("Persist the verified draft on the isolated prepublish branch",
                                 "Produce outcome using Editor-in-Chief freshness targets")), "not-cache-only-failure")
    require(any(row.get("id") == 114124281051 and row.get("name") == "workers (0)"
                and row.get("conclusion") == "success" for row in jobs), "exact-accepted-worker-missing")
    payload = copy.deepcopy(draft["value"])
    provenance = payload.pop("eicEditorialTrial", None)
    require(isinstance(provenance, dict), "missing-original-stamp")
    engine = original.checked_engine(provenance.get("producerEngine"))
    require(engine == original.producer_engine("false", "false", "true"), "not-reviewed-google-engine")
    expected = {"contractRevision": REVISION, "dispatcherRunId": claim["dispatcherRunId"],
                "childRunId": CHILD, "claimPath": ORIGINAL_ROOT + ".claim.json",
                "draftPayloadSHA256": original.digest(payload), "reviewedSources": original.REVIEWED_SOURCES,
                "producerEngine": engine}
    require(provenance == expected and payload.get("draftId") != claim.get("priorDraftId")
            and payload.get("status") == "VERIFIED_DRAFT" and payload.get("publicationType") == "LIVE"
            and isinstance(payload.get("articles"), list) and payload["articles"]
            and not draft_has_locator_only_sources(payload), "persisted-payload-not-bound")
    # REAL audit now: no backdated call, no monkeypatch of original TTL gates.
    # Only original content/canonical validation is reused, not trial authority.
    for article in payload["articles"]:
        require(start <= current.checked_clock(article.get("verifiedAt"), now) <= expiry
                and original.canonical_article_ok(article, claim, now), "original-content-gates-failed-at-audit-now")
    publish = read_action(store, PUBLISH_RUN)
    require(publish and str(publish.get("id")) == PUBLISH_RUN and publish.get("status") == "completed"
            and publish.get("conclusion") == "success" and publish.get("name") == "Live Publication Auto Maintenance"
            and publish.get("head_sha") == PUBLISH_HEAD and publish.get("head_branch") == "main"
            and publish.get("path") == ".github/workflows/live-publication-maintenance.yml"
            and publish.get("event") == "workflow_dispatch"
            and type(publish.get("run_attempt")) is int and publish["run_attempt"] == 1
            and publish.get("repository", {}).get("full_name") == current.REPOSITORY,
            "owner-publication-not-proven")
    live = store.published_live()
    require(live["sha"] == PUBLISHED_LIVE_SHA and live["value"].get("coverage", {}).get("verifiedDraftId") == payload["draftId"]
            and live["value"].get("coverage", {}).get("verifiedDraftCreatedAt") == payload["createdAt"],
            "immutable-publication-anchor-changed")
    import promote_verified_live_draft as publisher
    target, articles = publisher.validate_draft(payload, now, 8, 90)
    expected_items = publisher.build_live(payload, {"items": [], "coverage": {}}, {}, target, articles)["items"]
    require(live["value"].get("items") == expected_items
            and publisher.parse_iso(live["value"].get("lastUpdated")) == target,
            "published-payload-differs")
    return payload, engine


def audit(root, original, store, owner, now, *, clock=None):
    clock = clock or (lambda: datetime.now(timezone.utc))
    require(owner.get("workflow") == "Editor-in-Chief Newsroom Assignment"
            and str(owner.get("runId", "")).isdigit(), "wrong-owner")
    if not current.parse_stamp(APPROVED_AT, "proof-audit") <= now <= current.parse_stamp(APPROVAL_END, "proof-audit"):
        return {"audited": False, "reason": "separate-human-approval-window-closed"}
    if store.read(AUDIT_ROOT + ".claim.json") is not None:
        return {"audited": False, "reason": "one-proof-audit-already-consumed"}
    store.create(AUDIT_ROOT + ".claim.json", {"owner": "Site Editor-in-Chief", "runId": owner["runId"],
        "humanApprovalAt": APPROVED_AT, "claimedAt": current.iso(now), "expiresAt": APPROVAL_END,
        "scope": "independent-existing-persisted-and-published-draft-proof-only",
        "originalTrialExpiryExtended": False, "sourceCalls": 0, "modelCalls": 0, "remainingAttempts": 0})
    record = {"owner": "Site Editor-in-Chief", "runId": owner["runId"], "checkedAt": current.iso(now),
              "sourceCalls": 0, "modelCalls": 0, "remainingAttempts": 0,
              "originalFailedResultSHA": RESULT_SHA, "originalTrialExpiryExtended": False,
              "publicationPermissionGranted": False, "editorialOutcomeVerified": False, "status": "PROOF_AUDIT_FAILED"}
    try:
        records = [store.read(ORIGINAL_ROOT + "." + kind + ".json") for kind in ("claim", "run", "result")]
        draft = store.read(current.DRAFT_PATH); capacity = store.read(current.CAPACITY_PATH)
        payload, engine = prove(root, original, store, now, records, draft, capacity)
        require(now <= clock() <= current.parse_stamp(APPROVAL_END, "proof-audit"), "approval-expired-during-proof")
        require(store.read(current.DRAFT_PATH) == draft and store.read(ORIGINAL_ROOT + ".result.json") == records[2],
                "proof-race-before-record")
        record.update(status="VERIFIED_EXISTING_PRODUCTION_PROOF", editorialOutcomeVerified=True,
                      persistedDraftSHA=DRAFT_SHA, draftId=payload["draftId"], publishedCommit=PUBLISHED_COMMIT,
                      publishedLiveSHA=PUBLISHED_LIVE_SHA, childRunId=CHILD, reviewedSources=original.REVIEWED_SOURCES,
                      originalTrialExpiredAt=records[0]["value"]["expiresAt"], **engine)
    except (Exception, SystemExit) as exc:
        record["failureCode"] = exc.code if isinstance(exc, current.ProbeFailure) else type(exc).__name__
    store.create(AUDIT_ROOT + ".result.json", record)
    if record["status"] != "VERIFIED_EXISTING_PRODUCTION_PROOF":
        return {"audited": False, "reason": record["failureCode"]}
    if store.read(current.DRAFT_PATH) != draft or store.read(ORIGINAL_ROOT + ".result.json") != records[2]:
        return {"audited": False, "reason": "proof-race-before-capacity-cas"}
    if not now <= clock() <= current.parse_stamp(APPROVAL_END, "proof-audit"):
        return {"audited": False, "reason": "approval-expired-before-capacity-cas"}
    value = copy.deepcopy(capacity["value"])
    value.update(status="DEGRADED_LOCAL_FALLBACK", checkedAt=current.iso(now), blockedUntil=None,
        reason="Human-approved Site EIC independently proved exact original Google production and normal publication; original failed trial retained",
        capabilityOnly=False, editorialOutcomeVerified=True, publicationPermissionGranted=False,
        verifiedEngine="LOCAL_GEMMA", localFallbackModel=current.MODEL, workflowRunId=CHILD,
        recoveryOwner="workflow:general-news-producer.yml", verifiedDraftId=payload["draftId"], verifiedDraftSHA=DRAFT_SHA,
        structuredCopyPathSkipped=False, editorialProofAuditPath=AUDIT_ROOT + ".result.json",
        originalFailedTrialResultSHA=RESULT_SHA, editorialTrialLedgerBranch=current.LEDGER_BRANCH)
    return {"audited": store.compare_and_swap_capacity(CAPACITY_SHA, value), "sourceCalls": 0, "modelCalls": 0,
            "proofPath": AUDIT_ROOT + ".result.json"}


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--original-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        owner = current.context("eic")
        sys.path.insert(0, str(args.original_root / "scripts"))
        spec = importlib.util.spec_from_file_location("original_bound_editorial_trial", args.original_root / "scripts/editorial_revision_trial.py")
        original = importlib.util.module_from_spec(spec); spec.loader.exec_module(original)
        result = audit(args.original_root, original, AuditStore(os.environ.get("GH_TOKEN", ""), current.REPOSITORY),
                       owner, datetime.now(timezone.utc))
    except Exception as exc:
        result = {"audited": False, "reason": exc.code if isinstance(exc, current.ProbeFailure) else type(exc).__name__}
    print("EIC_HUMAN_APPROVED_PROOF_AUDIT " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
