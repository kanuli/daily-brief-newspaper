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
MODEL = "gemma3:4b-it-qat"
FAILED_MODEL = "gemma3:4b-it-qat"
FAILED_RUN = "37955233912"
FAILED_JOB = 113905133099
FAILED_HEAD = "2e12721182d544be4cb3634d50e01c0ef5eddd15"
FAILED_CAPACITY_SHA = "be7dbf9945fa0911bd6e0e136f9d647ba53c4b55"
FAILED_CHECKED_AT = "2026-10-09T15:58:07.688766Z"
MAX_RUNTIME_MINUTES = 20
PREDECESSOR_CONTRACT = "07c723dc652c32b51237c599fd082e8eb518dba75cf40ca565a658185ca5c1b1"
PREDECESSOR_RESULT_SHA = "f096c5a6f04d12a402638249e68c87ed6744a030"
PREDECESSOR_CHILD = "37950761065"
PREDECESSOR_HEAD = "932bb166cb4b52ba1be096ff797dbfdb0c462216"
PREDECESSOR_JOB = 113890880726
FALLBACK_BIND_DEADLINE_SECONDS = 660
# Fixed reviewed BEHAVIOR, not source/HEAD/clock: cosmetic source edits cannot
# mint another immutable ledger path. Exact reviewed code is a separate check.
CONTRACT = {
    "protocol": "google-gemma-rthk-exact-article-body-extraction-v11", "model": MODEL,
    "modelDeveloper": "Google DeepMind", "ownerPolicy": "non-China-developed-models-only",
    "modelManifestDigest": "b0313423c9448adfab711aacbc9d0b885a390eb31f1145d7f8495d1e6f84f257",
    "verifiedRuntimePredecessor": {"run": PREDECESSOR_CHILD, "head": PREDECESSOR_HEAD, "job": PREDECESSOR_JOB},
    "publisherBodyExtraction": {
        "host": "news.rthk.hk", "scheme": "https", "port": "default-or-443",
        "path": "/rthk/ch/component/k2/<digits>-<eight-digit-date>.htm",
        "queryAndFragment": "none", "body": "div-with-exact-itemFullText-class-token",
        "excluded": ["metadata", "navigation", "footer", "script", "style", "noscript", "svg"],
        "minimumActualBodyCharacters": 300, "maximumSourceCharacters": 9000,
        "observedFailure": "twelve-source-probes-zero-model-calls-original-parser-missed-div-body",
        "measuredFailedArticles": {"1873366": 427, "1873291": 228, "1873367": 199, "1873345": 128},
        "shortArticlePolicy": "reject-without-metadata-padding-or-search-snippet-substitution",
    },
    "runtimeOwnership": {"loopbackPort": 11435, "daemon": "one-worker-owned-clean-environment-process",
                         "modelStore": "explicit-cache-matching-model-directory",
                         "parallelRequests": 1, "loadedModels": 1,
                         "warmup": "empty-prompt-load-only-no-generated-tokens",
                         "warmupSeconds": 60, "budget": "inside-original-shared-deadline-no-renewal",
                         "proof": "exact-loaded-model-digest-and-observed-resource-scalars",
                         "observedFailure": "installer-daemon-port-conflict-obscured-runtime-plus-two-240-second-timeouts"},
    "execution": {"workers": 3, "maxParallel": 3, "deskPartition": "distinct-index-modulo-three",
                  "maxSourceProbesPerWorker": 4, "maxModelCallsPerWorker": 1,
                  "childBindings": 1, "canonicalProducerJobs": 1,
                  "sourcePlan": "exact-run-code-request-staging-and-state-digests",
                  "deadline": "fixed-shared-plan-deadline-no-worker-renewal",
                  "enginePolicy": "reviewed-Google-local-only-no-unpinned-Copilot"},
    "candidateIdentity": "exact-candidate-id-enum",
    "copyFields": ["title", "dek", "summary", "body", "context", "why", "watchNext"],
    "copyFieldsRequired": True, "copyStringsNonempty": True,
    "bodyRepresentation": "two-or-three-source-paragraphs-serialized-with-double-newline",
    "predecessorContract": PREDECESSOR_CONTRACT,
    "observedPriorProductionFailure": "three-small-model-completions-rejected-for-kana-or-supplied-paragraph-representation",
    "priorFailedProduction": {"run": FAILED_RUN, "job": FAILED_JOB, "head": FAILED_HEAD, "model": FAILED_MODEL},
    "dailyBody": {"visibleMinimum": 100, "visibleMaximum": 1800, "paragraphCharactersMinimum": 60, "paragraphCharactersMaximum": 110},
    "boundedCopy": {"paragraphs": 2, "factCharactersMaximum": 100,
                    "fieldCharacterLimits": {"title": 40, "dek": 60, "summary": 80, "context": 60, "why": 50, "watchNext": 50},
                    "policy": "source-faithful-concise-copy-no-truncation-padding-or-output-repair"},
    "copyLanguageRepresentation": "literal-cjk-leading-single-line-fields-and-body-paragraphs",
    "copyGrammarExcludes": ["U+3040-U+30FF", "U+FF66-U+FF9F"],
    "observedGoogleFailure": "CJK-leading-copy-with-excessive-kana-correctly-rejected",
    "modelContextTokens": 32768,
    "truncateInput": False,
    "shiftContext": False,
    "trustedPolicyInstructions": True, "nativeSystemRole": False,
    "trustedInstructionTransport": "initial-user-prompt-plus-final-after-input-reminder",
    "localeInstructionPosition": "original-prefix-plus-trusted-after-input-reminder",
    "sourceSelection": {
        "mode": "availability-aware-round-robin-v1", "maxCandidatesPerDesk": 4,
        "maxSourceProbes": 12, "maxModelCalls": 3, "maxAcceptedPerDesk": 1,
        "sourceWorkerTimeoutSeconds": 35, "sharedFallbackSeconds": 600,
        "bindDeadlineSeconds": FALLBACK_BIND_DEADLINE_SECONDS,
    },
    "factsMinimum": 2, "factsMaximum": 5,
    "gatePolicy": "existing-valid-output-and-canonical-merge-unchanged",
}
REVIEWED_SOURCES = {
    "scripts/general_news_local_fallback.py": "6c60ee527518aa3d40df8d7ff0ebc21d79da51f137936fb90c7d97467282d26b",
    "scripts/parallel_general_news_fallback.py": "c5247c9d38338d37cebada3630feac4b4437cd650f07c1fc2eb03a2a2453aa0c",
    ".github/workflows/general-news-producer.yml": "1caacbf6c61e90accf2f1c53a51aeeb132180afc082641b5e480c574480ae932",
    "scripts/owned_general_news_runtime.py": "f1522b4d906d34c9a6e8c2bd9a2c9f7b8f69c7d298c9b91eb6d0dbacf107a1db",
    "scripts/general_news_verified_producer.py": "b8604594ee18a5f7bc31d68acb0fb175ec752b73dc9f5970e1cd207ca2f37e2d",
    "scripts/general_news_verification_robot.py": "1c37dbb561bfb49863284f5a28793a71ed3df181d7efe60482258da9336f21e9",
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
        "verifiedEngine": "LOCAL_GEMMA" if local else "COPILOT",
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


def failed_production_proven(store) -> bool:
    """Read-only exact completed run/job evidence; never creates a retry."""
    try:
        def read(path):
            return store.json_request(urllib.request.Request(
                f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{FAILED_RUN}{path}",
                headers=store.headers(), method="GET"))
        run = read("")
        if (not isinstance(run, dict) or type(run.get("id")) is not int
            or str(run["id"]) != FAILED_RUN or run.get("repository", {}).get("full_name") != REPOSITORY
            or run.get("name") != "General News Verified Producer"
            or run.get("path") != ".github/workflows/general-news-producer.yml"
            or run.get("head_branch") != "main" or run.get("head_sha") != FAILED_HEAD
            or run.get("event") != "workflow_dispatch" or type(run.get("run_attempt")) is not int
            or run["run_attempt"] != 1 or run.get("status") != "completed" or run.get("conclusion") != "failure"):
            return False
        jobs = read("/jobs?per_page=100").get("jobs")
        if not isinstance(jobs, list):
            return False
        matching = [job for job in jobs if isinstance(job, dict) and type(job.get("id")) is int and job["id"] == FAILED_JOB]
        if len(matching) != 1:
            return False
        job = matching[0]
        return (job.get("run_id") == int(FAILED_RUN) and job.get("name") == "produce"
                and job.get("status") == "completed" and job.get("conclusion") == "failure"
                and any(isinstance(step, dict) and step.get("name") == "Fail non-capacity verification/copy errors"
                        and step.get("conclusion") == "failure" for step in job.get("steps", [])))
    except Exception:
        return False


def verified_predecessor_proven(store) -> bool:
    """Require the exact spent successful Google runtime trial, not a reset."""
    try:
        def read(path):
            return store.json_request(urllib.request.Request(
                f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{PREDECESSOR_CHILD}{path}",
                headers=store.headers(), method="GET"))
        run = read("")
        if (not isinstance(run, dict) or type(run.get("id")) is not int
            or str(run["id"]) != PREDECESSOR_CHILD or run.get("repository", {}).get("full_name") != REPOSITORY
            or run.get("name") != "General News Verified Producer"
            or run.get("path") != ".github/workflows/general-news-producer.yml"
            or run.get("head_branch") != "main" or run.get("head_sha") != PREDECESSOR_HEAD
            or run.get("event") != "workflow_dispatch" or type(run.get("run_attempt")) is not int
            or run["run_attempt"] != 1 or run.get("status") != "completed" or run.get("conclusion") != "success"):
            return False
        jobs = read("/jobs?per_page=100").get("jobs")
        if not isinstance(jobs, list):
            return False
        matching = [job for job in jobs if isinstance(job, dict) and type(job.get("id")) is int and job["id"] == PREDECESSOR_JOB]
        if len(matching) != 1:
            return False
        job = matching[0]
        return (job.get("run_id") == int(PREDECESSOR_CHILD) and job.get("name") == "produce"
                and job.get("status") == "completed" and job.get("conclusion") == "success"
                and any(isinstance(step, dict) and step.get("name") == "Finalize reviewed trial from exact persisted draft or preserve failed capacity"
                        and step.get("conclusion") == "success" for step in job.get("steps", [])))
    except Exception:
        return False


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
        or capacity["value"].get("localFallbackModel") != FAILED_MODEL
        or capacity["value"].get("capabilityOnly") is True):
        return {"eligible": False, "reason": "base-editorial-failure-changed"}
    checked_clock(capacity["value"]["checkedAt"], now)
    predecessor = store.read(f"{TRIAL_ROOT}/{PREDECESSOR_CONTRACT}.result.json")
    if (not predecessor or predecessor["sha"] != PREDECESSOR_RESULT_SHA
        or predecessor["value"].get("contractRevision") != PREDECESSOR_CONTRACT
        or predecessor["value"].get("status") != "VERIFIED_NEW_DRAFT"
        or predecessor["value"].get("childRunId") != PREDECESSOR_CHILD
        or predecessor["value"].get("editorialOutcomeVerified") is not True
        or predecessor["value"].get("verifiedEngine") != "LOCAL_GEMMA"
        or predecessor["value"].get("publicationPermissionGranted") is not False
        or predecessor["value"].get("remainingAttempts") != 0):
        return {"eligible": False, "reason": "reviewed-successful-predecessor-record-not-proven"}
    if store.read(record_path("claim")) is not None:
        from editorial_trial_observation import observe_pending_trial
        observation = observe_pending_trial(
            store=store, now=now, repository=REPOSITORY,
            contract_revision=CONTRACT_REVISION, contract=CONTRACT,
            reviewed_sources=REVIEWED_SOURCES, prior_capacity_sha=capacity["sha"],
            prior_capacity=capacity["value"],
        )
        return {
            **observation, "eligible": False, "reason": "semantic-trial-budget-consumed",
            "owner": "Site Editor-in-Chief", "contractRevision": CONTRACT_REVISION,
            "checkedAt": iso(now), "capacitySHA": capacity["sha"],
            "priorCapacity": capacity["value"], "capacityRemainsFailed": True,
            "publicationPermissionGranted": False,
        }
    if not failed_production_proven(store):
        return {"eligible": False, "reason": "exact-prior-editorial-production-failure-not-proven"}
    if not verified_predecessor_proven(store):
        return {"eligible": False, "reason": "exact-successful-predecessor-trial-not-proven"}
    return {
        "eligible": True, "owner": "Site Editor-in-Chief",
        "contractRevision": CONTRACT_REVISION, "dispatcherRunId": owner["runId"],
        "checkedAt": iso(now), "capacitySHA": capacity["sha"],
        "priorCapacity": capacity["value"], "capacityRemainsFailed": True,
        "predecessorResultSHA": PREDECESSOR_RESULT_SHA,
        "failedProduction": CONTRACT["priorFailedProduction"],
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
        "failedProduction": copy.deepcopy(CONTRACT["priorFailedProduction"]),
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
        or state.get("failedProduction") != CONTRACT["priorFailedProduction"]
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
    body = article.get("body")
    if not isinstance(body, str) or not 100 <= len(re.sub(r"\s+", "", body)) <= 1800:
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
    local = result["verifiedEngine"] == "LOCAL_GEMMA"
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
            # Real child-bind clock, not a workflow input or retry reset.
            # Preserve time for persistence inside the existing 15-minute job.
            handle.write("fallback_deadline_unix=" + str(now.timestamp() + FALLBACK_BIND_DEADLINE_SECONDS) + "\n")
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
