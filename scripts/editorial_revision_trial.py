#!/usr/bin/env python3
"""One reviewed Site EIC editorial-code trial, never runtime-capacity recovery.

No model/source calls occur here. Failed producer capacity stays failed until
the existing pinned strict producer creates AND persists a genuinely new draft.
Create-only claim, child-run and result records live outside publication state.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

from probe_general_news_fallback_capability import (
    GitHubCapacityStore, ProbeFailure, REPOSITORY, LEDGER_BRANCH, CAPACITY_BRANCH,
    CAPACITY_PATH, parse_stamp, save_json, load_json,
)

DRAFT_PATH = "data/prepublish.json"
TRIAL_ROOT = "data/producer-editorial-trials"
MODEL = "qwen2.5:1.5b"
FAILED_RUN = "37805090332"
FAILED_CAPACITY_SHA = "3c2541d5c9ff3619b49abdcef4c1333bbc259275"
FAILED_CHECKED_AT = "2026-10-08T16:03:29.435752Z"
MAX_RUNTIME_MINUTES = 20
PREDECESSOR_CONTRACT = "eb53e7505f72f8071c3abdef4a17d89673fc5c3006aaba6493299fbe2cad67a7"
PREDECESSOR_RESULT_SHA = "4961499c24285914e6ad9914b31671280613df40"
PREDECESSOR_CHILD = "37882927467"
# Fixed reviewed BEHAVIOR, not source/HEAD/clock: cosmetic source edits cannot
# mint another immutable ledger path. Exact reviewed code is a separate check.
CONTRACT = {
    "protocol": "ollama-structured-paragraph-copy-v2", "model": MODEL,
    "candidateIdentity": "exact-candidate-id-enum",
    "copyFields": ["title", "dek", "summary", "body", "context", "why", "watchNext"],
    "copyFieldsRequired": True, "copyStringsNonempty": True,
    "bodyRepresentation": "two-or-three-source-paragraphs-serialized-with-double-newline",
    "predecessorContract": PREDECESSOR_CONTRACT,
    "observedPredecessorFailure": "body-paragraph-break-missing",
    "factsMinimum": 2, "factsMaximum": 5,
    "gatePolicy": "existing-valid-output-and-canonical-merge-unchanged",
}
REVIEWED_SOURCES = {
    "scripts/general_news_local_fallback.py": "7b004f7f18174e7f74bce51ef755ec067a8e9bfba23091b9a9686c653b94f395",
    "scripts/general_news_verified_producer.py": "b8604594ee18a5f7bc31d68acb0fb175ec752b73dc9f5970e1cd207ca2f37e2d",
    "scripts/general_news_verification_robot.py": "5e60639ab28729975e8f8543efe669b2e11af77e7667913f13b1e33a3dd1b6f5",
}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


CONTRACT_REVISION = digest(CONTRACT)


def record_path(kind: str) -> str:
    if kind not in {"claim", "run", "result"}:
        raise ProbeFailure("trial", "invalid-record-kind")
    return f"{TRIAL_ROOT}/{CONTRACT_REVISION}.{kind}.json"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def checked_clock(value, now: datetime) -> datetime:
    parsed = parse_stamp(value, "trial")
    if parsed > now:
        raise ProbeFailure("trial", "future-clock")
    return parsed


def producer_engine(verify_ok: str, copy_ok: str, local_ok: str) -> dict:
    """Use trusted producer step outputs, never trial inputs or draft flags."""
    if any(value not in {"", "false", "true"} for value in (verify_ok, copy_ok, local_ok)):
        raise ProbeFailure("trial-engine", "invalid-step-output")
    copilot = verify_ok == "true" and copy_ok == "true"
    local = local_ok == "true"
    if copilot == local:
        raise ProbeFailure("trial-engine", "missing-or-conflicting-engine-evidence")
    return {
        "verifiedEngine": "LOCAL_QWEN" if local else "COPILOT",
        "copilotVerificationSucceeded": verify_ok == "true",
        "copilotCopySucceeded": copy_ok == "true",
        "localFallbackSucceeded": local,
        "structuredCopyPathSkipped": copilot,
    }


def checked_engine(value) -> dict:
    if not isinstance(value, dict):
        raise ProbeFailure("trial-engine", "missing-engine-evidence")
    fields = ("copilotVerificationSucceeded", "copilotCopySucceeded", "localFallbackSucceeded")
    if any(type(value.get(field)) is not bool for field in fields):
        raise ProbeFailure("trial-engine", "invalid-engine-evidence")
    expected = producer_engine(*(str(value[field]).lower() for field in fields))
    if value != expected:
        raise ProbeFailure("trial-engine", "inconsistent-engine-provenance")
    return expected


def reviewed_code(root: Path) -> bool:
    return all((root / name).is_file() and hashlib.sha256((root / name).read_bytes()).hexdigest() == expected
               for name, expected in REVIEWED_SOURCES.items())


def context(role: str) -> dict:
    required_workflow = "Editor-in-Chief Newsroom Assignment" if role == "eic" else "General News Verified Producer"
    run = os.environ.get("GITHUB_RUN_ID", "")
    if (os.environ.get("GITHUB_REPOSITORY") != REPOSITORY
        or os.environ.get("GITHUB_WORKFLOW") != required_workflow
        or not re.fullmatch(r"[1-9][0-9]*", run)
        or os.environ.get("GITHUB_RUN_ATTEMPT") != "1"):
        raise ProbeFailure("trial", "invalid-owner-or-rerun")
    return {"workflow": required_workflow, "runId": run}


class TrialStore(GitHubCapacityStore):
    @staticmethod
    def allowed_path(path: str) -> bool:
        return path == CAPACITY_PATH or bool(re.fullmatch(
            re.escape(TRIAL_ROOT) + r"/[0-9a-f]{64}\.(claim|run|result)\.json", path))

    def request(self, method: str, path: str, payload=None):
        if path == DRAFT_PATH:
            if method != "GET" or payload is not None:
                raise ProbeFailure("trial-store", "draft-read-only")
            req = urllib.request.Request(
                f"https://api.github.com/repos/{REPOSITORY}/contents/{DRAFT_PATH}?ref={CAPACITY_BRANCH}",
                headers=self.headers(), method="GET")
            return self.json_request(req)
        return super().request(method, path, payload)

    def create(self, path: str, value: dict) -> None:
        if not path.startswith(TRIAL_ROOT + "/"):
            raise ProbeFailure("trial-store", "immutable-ledger-only")
        self.request("PUT", path, {
            "message": "Record bounded Site EIC editorial-code trial",
            "branch": LEDGER_BRANCH,
            "content": base64.b64encode(json.dumps(value, ensure_ascii=False, indent=2).encode()).decode(),
        })


def eligible(root: Path, store, owner: dict, now: datetime) -> dict:
    if not reviewed_code(root):
        return {"eligible": False, "reason": "unreviewed-code"}
    if not store.ledger_ready():
        return {"eligible": False, "reason": "ledger-unavailable"}
    capacity = store.read(CAPACITY_PATH)
    if (not capacity or capacity["sha"] != FAILED_CAPACITY_SHA
        or capacity["value"].get("status") != "LOCAL_FALLBACK_FAILED"
        or capacity["value"].get("workflowRunId") != FAILED_RUN
        or capacity["value"].get("checkedAt") != FAILED_CHECKED_AT
        or capacity["value"].get("localFallbackModel") != MODEL
        or capacity["value"].get("capabilityOnly") is True):
        return {"eligible": False, "reason": "base-editorial-failure-changed"}
    checked_clock(capacity["value"]["checkedAt"], now)
    predecessor = store.read(f"{TRIAL_ROOT}/{PREDECESSOR_CONTRACT}.result.json")
    if (not predecessor or predecessor["sha"] != PREDECESSOR_RESULT_SHA
        or predecessor["value"].get("status") != "EDITORIAL_TRIAL_FAILED"
        or predecessor["value"].get("childRunId") != PREDECESSOR_CHILD
        or predecessor["value"].get("editorialOutcomeVerified") is not False):
        return {"eligible": False, "reason": "reviewed-predecessor-failure-not-proven"}
    if store.read(record_path("claim")) is not None:
        return {"eligible": False, "reason": "semantic-trial-budget-consumed"}
    return {
        "eligible": True, "owner": "Site Editor-in-Chief",
        "contractRevision": CONTRACT_REVISION, "dispatcherRunId": owner["runId"],
        "checkedAt": iso(now), "capacitySHA": capacity["sha"],
        "priorCapacity": capacity["value"], "capacityRemainsFailed": True,
        "predecessorResultSHA": PREDECESSOR_RESULT_SHA,
        "publicationPermissionGranted": False,
    }


def claim(root: Path, store, permit: dict, assignment: dict, owner: dict, now: datetime) -> dict:
    # Re-read exact capacity/code/immutable ledger. A permit alone is never authority.
    fresh = eligible(root, store, owner, now)
    if (fresh.get("eligible") is not True or permit.get("eligible") is not True
        or permit.get("dispatcherRunId") != owner["runId"]
        or permit.get("contractRevision") != CONTRACT_REVISION
        or permit.get("capacitySHA") != FAILED_CAPACITY_SHA
        or (now - checked_clock(permit.get("checkedAt"), now)).total_seconds() > 300
        or assignment.get("robot") != "general-producer"
        or assignment.get("workflow") != "general-news-producer.yml"
        or assignment.get("status") != "reviewed-editorial-trial"
        or assignment.get("dispatchable") is not True
        or assignment.get("dispatchInputs") != {
            "editorial_trial_contract": CONTRACT_REVISION,
            "editorial_trial_dispatcher_run": owner["runId"],
        }):
        raise ProbeFailure("trial-claim", "admission-not-authorized")
    old_draft = store.read(DRAFT_PATH)
    state = {
        "schemaVersion": 1, "owner": "Site Editor-in-Chief",
        "scope": "single-reviewed-editorial-code-trial",
        "contractRevision": CONTRACT_REVISION, "contract": CONTRACT,
        "reviewedSources": REVIEWED_SOURCES,
        "claimedAt": iso(now), "expiresAt": iso(now + timedelta(minutes=MAX_RUNTIME_MINUTES)),
        "dispatcherRunId": owner["runId"], "assignmentId": assignment["assignmentId"],
        "attempt": 1, "maxAttempts": 1, "remainingAttempts": 0,
        "priorCapacitySHA": FAILED_CAPACITY_SHA, "priorCapacity": copy.deepcopy(fresh["priorCapacity"]),
        "predecessorResultSHA": PREDECESSOR_RESULT_SHA,
        "priorDraftId": (old_draft or {}).get("value", {}).get("draftId"),
        "publicationPermissionGranted": False,
    }
    store.create(record_path("claim"), state)  # Conflict/failure is fatal, never fallback dispatch.
    return state


def bind(root: Path, store, contract: str, dispatcher: str, child: dict, now: datetime) -> dict | None:
    capacity = store.read(CAPACITY_PATH)
    if not contract and not dispatcher:
        if capacity and capacity["value"].get("status") == "LOCAL_FALLBACK_FAILED":
            raise ProbeFailure("trial-bind", "failed-capacity-requires-reviewed-eic-trial")
        return None
    claimed = store.read(record_path("claim"))
    state = (claimed or {}).get("value", {})
    if (contract != CONTRACT_REVISION or not reviewed_code(root)
        or not claimed or state.get("owner") != "Site Editor-in-Chief"
        or state.get("contractRevision") != CONTRACT_REVISION
        or state.get("reviewedSources") != REVIEWED_SOURCES or state.get("contract") != CONTRACT
        or state.get("dispatcherRunId") != dispatcher
        or state.get("priorCapacitySHA") != FAILED_CAPACITY_SHA
        or state.get("predecessorResultSHA") != PREDECESSOR_RESULT_SHA
        or state.get("priorCapacity", {}).get("workflowRunId") != FAILED_RUN
        or not capacity or capacity["sha"] != FAILED_CAPACITY_SHA
        or state.get("attempt") != 1 or state.get("remainingAttempts") != 0
        or state.get("publicationPermissionGranted") is not False):
        raise ProbeFailure("trial-bind", "immutable-claim-not-authorized")
    checked_clock(state.get("claimedAt"), now)
    expiry = parse_stamp(state.get("expiresAt"), "trial-bind")
    if expiry - parse_stamp(state["claimedAt"], "trial-bind") != timedelta(minutes=MAX_RUNTIME_MINUTES) or now > expiry:
        raise ProbeFailure("trial-bind", "claim-expired-or-invalid")
    run = {"schemaVersion": 1, "contractRevision": CONTRACT_REVISION,
           "dispatcherRunId": dispatcher, "childRunId": child["runId"], "boundAt": iso(now),
           "claimPath": record_path("claim"), "reviewedSources": REVIEWED_SOURCES}
    store.create(record_path("run"), run)  # A second child or rerun cannot consume the same claim.
    return {"claim": state, "run": run}


def verify_state(root: Path, store, state: dict, child: dict, now: datetime) -> dict:
    claimed = store.read(record_path("claim"))
    bound = store.read(record_path("run"))
    if (not reviewed_code(root) or not claimed or not bound
        or claimed["value"] != state.get("claim") or bound["value"] != state.get("run")
        or bound["value"].get("childRunId") != child["runId"]
        or bound["value"].get("reviewedSources") != REVIEWED_SOURCES
        or claimed["value"].get("contractRevision") != CONTRACT_REVISION):
        raise ProbeFailure("trial-output", "claim-child-code-binding-failed")
    claimed_at = checked_clock(claimed["value"].get("claimedAt"), now)
    bound_at = checked_clock(bound["value"].get("boundAt"), now)
    expiry = parse_stamp(claimed["value"].get("expiresAt"), "trial-output")
    if bound_at < claimed_at or expiry - claimed_at != timedelta(minutes=MAX_RUNTIME_MINUTES):
        raise ProbeFailure("trial-output", "invalid-binding-clock")
    if now > expiry:
        raise ProbeFailure("trial-output", "trial-runtime-expired")
    return claimed["value"]


def stamp_draft(root: Path, store, state: dict, draft: dict, child: dict, now: datetime, *, engine=None) -> dict:
    claimed = verify_state(root, store, state, child, now)
    engine = checked_engine(engine)
    created = checked_clock(draft.get("createdAt"), now)
    if (draft.get("status") != "VERIFIED_DRAFT" or draft.get("publicationType") != "LIVE"
        or not isinstance(draft.get("articles"), list) or not draft["articles"]
        or not all(canonical_article_ok(row, claimed, now) for row in draft["articles"])
        or not draft.get("draftId") or draft["draftId"] == claimed.get("priorDraftId")
        or created < parse_stamp(claimed["claimedAt"], "trial-output")):
        raise ProbeFailure("trial-output", "no-genuinely-new-verified-draft")
    stamped = copy.deepcopy(draft)
    stamped["eicEditorialTrial"] = {
        "contractRevision": CONTRACT_REVISION, "dispatcherRunId": claimed["dispatcherRunId"],
        "childRunId": child["runId"], "claimPath": record_path("claim"),
        "draftPayloadSHA256": digest(draft), "reviewedSources": REVIEWED_SOURCES,
        "producerEngine": engine,
    }
    return stamped


def canonical_article_ok(article, claimed: dict, now: datetime) -> bool:
    """Re-run the pinned existing copy/candidate gate and exact canonical build.

    This is a validation-only call: it performs no source fetch or generation.
    Original strict source grounding/merge precedes canonical production; this
    extra proof refuses shape-only flags or a different concurrent child draft.
    """
    import general_news_verified_producer as producer
    import general_news_verification_robot as verification_robot
    if not isinstance(article, dict):
        return False
    verification = article.get("verification") or {}
    evidence = article.get("sources") or []
    if (not isinstance(verification, dict) or not verification.get("candidateId")
        or verification.get("cantoneseCopyVerified") is not True
        or verification.get("noUnsupportedDetail") is not True
        or not isinstance(evidence, list) or not evidence
        or not any(isinstance(row, dict) and isinstance(row.get("facts"), list)
                   and len(row["facts"]) >= 2 for row in evidence)):
        return False
    verified = checked_clock(article.get("verifiedAt"), now)
    if verified < parse_stamp(claimed["claimedAt"], "trial-output"):
        return False
    raw_desk = next((slug for slug, routes in producer.DESK_ROUTES.items()
                     if routes == article.get("deskSlugs")), article.get("desk"))
    candidate = {
        "id": verification["candidateId"], "desk": raw_desk, "title": verification.get("originalTitle"),
        "source": article.get("sourceName"), "url": article.get("sourceUrl"),
        "publishedAt": article.get("publishedAt"), "sourceEvidence": evidence,
        "verifiedCopy": {field: article.get(field) for field in producer.COPY_FIELDS},
        "provider": verification.get("provider"), "query": verification.get("query"),
    }
    # The production workflow calls produce_with_soft_policy, not the legacy
    # same-calendar-day producer policy. Re-run that exact pinned candidate
    # gate so a legitimate recent story across HKT midnight remains eligible.
    return (verification_robot.candidate_ok_soft(candidate, raw_desk, now, set(), set())
            and producer.build_article(candidate, raw_desk, verified) == article)


def finish(root: Path, store, state: dict, draft: dict | None, child: dict, now: datetime, *, engine=None) -> bool:
    # Failure records are best effort, but the claim remains permanently spent
    # even when this final step or its immutable result write is interrupted.
    result = {"schemaVersion": 1, "contractRevision": CONTRACT_REVISION,
              "owner": "Site Editor-in-Chief", "childRunId": child["runId"],
              "checkedAt": iso(now), "remainingAttempts": 0,
              "status": "EDITORIAL_TRIAL_FAILED", "publicationPermissionGranted": False}
    try:
        verify_state(root, store, state, child, now)
        engine = checked_engine(engine)
        if not isinstance(draft, dict):
            raise ProbeFailure("trial-output", "no-new-draft")
        payload = copy.deepcopy(draft)
        provenance = payload.pop("eicEditorialTrial", None)
        expected = stamp_draft(root, store, state, payload, child, now, engine=engine)
        if provenance != expected["eicEditorialTrial"]:
            raise ProbeFailure("trial-output", "draft-not-bound-to-this-child")
        persisted = store.read(DRAFT_PATH)
        if not persisted or persisted["value"] != draft:
            raise ProbeFailure("trial-output", "new-draft-not-persisted-exactly")
        result.update(status="VERIFIED_NEW_DRAFT", draftId=draft["draftId"],
                      persistedDraftSHA=persisted["sha"], draftPayloadSHA256=digest(payload),
                      reviewedSources=REVIEWED_SOURCES, editorialOutcomeVerified=True)
        result.update(engine)
    except Exception as exc:
        result["failureCode"] = exc.code if isinstance(exc, ProbeFailure) else type(exc).__name__
        result["editorialOutcomeVerified"] = False
    store.create(record_path("result"), result)
    if result["status"] != "VERIFIED_NEW_DRAFT":
        return False
    # Re-check after immutable proof creation and immediately before capacity
    # CAS. Capacity is a proven engine outcome, never latest publication health.
    still_persisted = store.read(DRAFT_PATH)
    if (not still_persisted or still_persisted["sha"] != result["persistedDraftSHA"]
        or still_persisted["value"] != draft):
        return False
    claimed = state["claim"]
    capacity = copy.deepcopy(claimed["priorCapacity"])
    local = result["verifiedEngine"] == "LOCAL_QWEN"
    capacity.update(status="DEGRADED_LOCAL_FALLBACK" if local else "AVAILABLE", checkedAt=iso(now), blockedUntil=None,
                    reason=("Existing strict producer created and persisted a new verified local-fallback draft; Copilot quota is not restored"
                            if local else "Existing strict Copilot verification and copy created and persisted a new verified draft; structured local-copy trial path was not used"),
                    capabilityOnly=False, editorialOutcomeVerified=True, publicationPermissionGranted=False,
                    localFallbackModel=MODEL if local else None, workflowRunId=child["runId"],
                    recoveryOwner="workflow:general-news-producer.yml",
                    editorialTrialClaimPath=record_path("claim"), editorialTrialResultPath=record_path("result"),
                    editorialTrialLedgerBranch=LEDGER_BRANCH, verifiedDraftId=draft["draftId"],
                    verifiedDraftSHA=result["persistedDraftSHA"], verifiedEngine=result["verifiedEngine"],
                    structuredCopyPathSkipped=result["structuredCopyPathSkipped"])
    return store.compare_and_swap_capacity(claimed["priorCapacitySHA"], capacity)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("inspect", "claim", "bind", "stamp-draft", "finish"))
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--permit", type=Path)
    parser.add_argument("--assignment-json")
    parser.add_argument("--state", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--contract", default="")
    parser.add_argument("--dispatcher", default="")
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args()
    store = TrialStore(os.environ.get("GH_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", ""))
    owner = context("eic" if args.mode in {"inspect", "claim"} else "child")
    now = now_utc()
    if args.mode == "inspect":
        try:
            permit = eligible(args.root, store, owner, now)
        except Exception as exc:
            permit = {"eligible": False, "reason": exc.code if isinstance(exc, ProbeFailure) else type(exc).__name__}
        save_json(args.permit, permit)
    elif args.mode == "claim":
        save_json(args.state, claim(args.root, store, load_json(args.permit),
                  json.loads(args.assignment_json), owner, now))
    elif args.mode == "bind":
        state = bind(args.root, store, args.contract, args.dispatcher, owner, now)
        if state is not None:
            save_json(args.state, state)
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write("active=" + ("true" if state is not None else "false") + "\n")
    elif args.mode == "stamp-draft":
        engine = producer_engine(os.environ.get("VERIFY_OK", ""), os.environ.get("COPY_OK", ""),
                                 os.environ.get("LOCAL_FALLBACK_OK", ""))
        save_json(args.draft, stamp_draft(args.root, store, load_json(args.state),
                  load_json(args.draft), owner, now, engine=engine))
    else:
        draft = load_json(args.draft) if args.draft.is_file() else None
        try:
            engine = producer_engine(os.environ.get("VERIFY_OK", ""), os.environ.get("COPY_OK", ""),
                                     os.environ.get("LOCAL_FALLBACK_OK", ""))
        except ProbeFailure:
            engine = None
        updated = finish(args.root, store, load_json(args.state), draft, owner, now, engine=engine)
        print("EIC_EDITORIAL_TRIAL_FINAL capacity-cas=" + str(updated).lower())
        return 0 if updated else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
