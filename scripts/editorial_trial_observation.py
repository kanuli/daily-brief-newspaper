"""Read-only observation of a single already-bound Site EIC editorial trial.

This helper grants no admission, retry, dispatch, publication or capacity
authority. Only a matching immutable claim/binding and a current GitHub child
run can establish bounded pending ownership. Unknown evidence fails closed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
import urllib.request


MAX_RUNTIME_MINUTES = 20
TRIAL_ROOT = "data/producer-editorial-trials"
CHILD_WORKFLOW = "General News Verified Producer"
CHILD_PATH = ".github/workflows/general-news-producer.yml"
ACTIVE_STATUSES = frozenset({"queued", "in_progress", "waiting", "requested", "pending"})


def _clock(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else None
    except (ValueError, TypeError):
        return None


def _run_id(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value) is not None


def _record(value):
    return (
        isinstance(value, dict)
        and isinstance(value.get("sha"), str) and bool(value["sha"])
        and isinstance(value.get("value"), dict)
    )


def _held(reason):
    return {"pending": False, "reason": reason}


def observe_pending_trial(
    *, store, now, repository, contract_revision, contract, reviewed_sources,
    prior_capacity_sha, prior_capacity, expiry_minutes=MAX_RUNTIME_MINUTES,
):
    """Return pending ownership only for the exact unexpired bound child.

    The calling inspector supplies its independently reviewed contract and
    exact held capacity. All ledger/API access is read-only. No result, clock,
    HEAD, missing response or API failure can mint a trial or prolong expiry.
    """
    if (
        not isinstance(now, datetime) or now.tzinfo is None
        or not isinstance(repository, str)
        or re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is None
        or not isinstance(contract_revision, str)
        or re.fullmatch(r"[0-9a-f]{64}", contract_revision) is None
        or not isinstance(contract, dict) or not isinstance(reviewed_sources, dict)
        or not isinstance(prior_capacity_sha, str) or not prior_capacity_sha
        or not isinstance(prior_capacity, dict)
        or prior_capacity.get("status") != "LOCAL_FALLBACK_FAILED"
        or prior_capacity.get("capabilityOnly") is True
        or type(expiry_minutes) is not int or expiry_minutes != MAX_RUNTIME_MINUTES
    ):
        return _held("invalid-observation-expectations")
    now = now.astimezone(timezone.utc)
    claim_path = f"{TRIAL_ROOT}/{contract_revision}.claim.json"
    run_path = f"{TRIAL_ROOT}/{contract_revision}.run.json"
    result_path = f"{TRIAL_ROOT}/{contract_revision}.result.json"
    try:
        claimed = store.read(claim_path)
        bound = store.read(run_path)
        result = store.read(result_path)
        if result is not None:
            return _held("trial-result-already-recorded")
        if not _record(claimed) or not _record(bound):
            return _held("immutable-claim-or-binding-missing")
        claim = claimed["value"]
        binding = bound["value"]
        if (
            type(claim.get("schemaVersion")) is not int or claim["schemaVersion"] != 1
            or claim.get("owner") != "Site Editor-in-Chief"
            or claim.get("scope") != "single-reviewed-editorial-code-trial"
            or claim.get("contractRevision") != contract_revision
            or claim.get("contract") != contract
            or claim.get("reviewedSources") != reviewed_sources
            or claim.get("priorCapacitySHA") != prior_capacity_sha
            or claim.get("priorCapacity") != prior_capacity
            or not _run_id(claim.get("dispatcherRunId"))
            or not isinstance(claim.get("assignmentId"), str) or not claim["assignmentId"]
            or any(type(claim.get(field)) is not int for field in ("attempt", "maxAttempts", "remainingAttempts"))
            or claim["attempt"] != 1 or claim["maxAttempts"] != 1 or claim["remainingAttempts"] != 0
            or claim.get("publicationPermissionGranted") is not False
        ):
            return _held("immutable-claim-not-matching-reviewed-trial")
        if (
            type(binding.get("schemaVersion")) is not int or binding["schemaVersion"] != 1
            or binding.get("contractRevision") != contract_revision
            or binding.get("reviewedSources") != reviewed_sources
            or binding.get("dispatcherRunId") != claim["dispatcherRunId"]
            or binding.get("claimPath") != claim_path
            or not _run_id(binding.get("childRunId"))
        ):
            return _held("immutable-child-binding-not-matching-reviewed-trial")
        claimed_at, bound_at, expires_at = (
            _clock(claim.get("claimedAt")), _clock(binding.get("boundAt")), _clock(claim.get("expiresAt"))
        )
        if (
            claimed_at is None or bound_at is None or expires_at is None
            or not (claimed_at <= bound_at <= now <= expires_at)
            or expires_at - claimed_at != timedelta(minutes=MAX_RUNTIME_MINUTES)
        ):
            return _held("trial-expired-or-invalid-binding-clock")
        child_id = binding["childRunId"]
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/actions/runs/{child_id}",
            headers=store.headers(), method="GET",
        )
        run = store.json_request(request)
        if (
            not isinstance(run, dict)
            or type(run.get("id")) is not int or str(run["id"]) != child_id
            or not isinstance(run.get("repository"), dict)
            or run["repository"].get("full_name") != repository
            or run.get("name") != CHILD_WORKFLOW or run.get("path") != CHILD_PATH
            or run.get("event") != "workflow_dispatch" or run.get("head_branch") != "main"
            or type(run.get("run_attempt")) is not int or run["run_attempt"] != 1
            or run.get("status") not in ACTIVE_STATUSES
            or "conclusion" not in run or run["conclusion"] is not None
        ):
            return _held("trusted-child-run-not-active-or-not-matching")
        # A result may have been recorded while the run metadata was read.
        # Refuse to report pending if that final immutable evidence is visible.
        if store.read(result_path) is not None:
            return _held("trial-result-already-recorded")
        return {
            "pending": True, "reason": "trusted-single-child-trial-in-flight",
            "contractRevision": contract_revision,
            "trialDispatcherRunId": claim["dispatcherRunId"],
            "trialChildRunId": child_id, "trialChildStatus": run["status"],
            "trialRunAttempt": 1, "trialClaimSHA": claimed["sha"],
            "trialBindingSHA": bound["sha"],
            "trialClaimedAt": claimed_at.isoformat().replace("+00:00", "Z"),
            "trialExpiresAt": expires_at.isoformat().replace("+00:00", "Z"),
        }
    except Exception:
        # Never include request objects, token-bearing headers or API bodies.
        return _held("trial-observation-unavailable")
