#!/usr/bin/env python3
"""Site-EIC-owned, one-attempt infrastructure capability probe.

Only the reviewed fallback/dependency revision may be probed. The claim and
result are immutable per-revision telemetry. This module never discovers news,
calls the article producer, writes drafts/news, or dispatches a workflow.
Runtime readiness is not editorial verification or permission to publish.
"""
from __future__ import annotations

import argparse
import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPOSITORY = "kanuli/daily-brief-newspaper"
CAPACITY_BRANCH = "prepublish-news"
LEDGER_BRANCH = "eic-capability-ledger"
CAPACITY_PATH = "data/producer-capacity.json"
LEDGER_ROOT = "data/producer-capability-probes"
REVIEWED_REVISION = "eb3707b28647cbb1a78a306446df9f4c7422f951dd1b63fbd851e5d9289c9a1e"
REVISION_FILES = (
    "scripts/general_news_local_fallback.py",
    "scripts/requirements-general-news-fallback.txt",
    "scripts/check_general_news_fallback_dependencies.py",
)
MODEL = "qwen2.5:1.5b"
PROBE_SCOPE = "dependencies-and-synthetic-local-model-only"
EXPECTED_SYNTHETIC = {"readiness": "ok", "value": 7}
SYNTHETIC_PROMPT = (
    "This is a synthetic software readiness check, not news. "
    'Return exactly this JSON object and nothing else: {"readiness":"ok","value":7}.'
)
MAX_JSON_BYTES = 262144
BLOCKED_STATUSES = {"LOCAL_FALLBACK_FAILED", "QUOTA_EXHAUSTED"}


class ProbeFailure(RuntimeError):
    def __init__(self, stage: str, code: str):
        self.stage = stage
        self.code = code
        super().__init__(stage + ":" + code)


def stamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def revision(root: Path) -> str:
    digest = hashlib.sha256()
    for name in REVISION_FILES:
        digest.update(name.encode("utf-8") + b"\0")
        digest.update((root / name).read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def claim_path(probe_revision: str) -> str:
    return f"{LEDGER_ROOT}/{probe_revision}.claim.json"


def result_path(probe_revision: str) -> str:
    return f"{LEDGER_ROOT}/{probe_revision}.result.json"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ProbeFailure("state", "non-object")
    return value


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class GitHubCapacityStore:
    """Restricted Contents API access: only isolated infrastructure telemetry."""
    def __init__(self, token: str, repository: str):
        if repository != REPOSITORY or not token:
            raise ProbeFailure("store", "repository-or-token-unavailable")
        self.token = token

    @staticmethod
    def allowed_path(path: str) -> bool:
        return path == CAPACITY_PATH or bool(re.fullmatch(
            re.escape(LEDGER_ROOT) + r"/[0-9a-f]{64}\.(claim|result)\.json", path
        ))

    def headers(self):
        return {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "DailyBriefEICCapabilityProbe/1.0",
        }

    def json_request(self, req):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                raise ProbeFailure("store", "redirect-rejected")

        try:
            opener = urllib.request.build_opener(NoRedirect())
            with opener.open(req, timeout=20) as response:
                raw = response.read(MAX_JSON_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if req.method == "GET" and exc.code == 404:
                return None
            # Never print API response bodies or token-bearing request objects.
            raise ProbeFailure("store", f"http-{exc.code}") from None
        except Exception:
            raise ProbeFailure("store", "transport-failed") from None
        if len(raw) > MAX_JSON_BYTES:
            raise ProbeFailure("store", "response-too-large")
        return json.loads(raw)

    def ledger_ready(self) -> bool:
        # Provisioning this isolated branch is a reviewed deployment operation,
        # never an automatic probe side effect. Shared publication branches may
        # be replaced; they cannot be the one-attempt budget's durable authority.
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPOSITORY}/branches/{LEDGER_BRANCH}",
            headers=self.headers(), method="GET",
        )
        return self.json_request(req) is not None

    def request(self, method: str, path: str, payload=None):
        if method not in {"GET", "PUT"} or not self.allowed_path(path):
            raise ProbeFailure("store", "path-outside-capability-telemetry")
        branch = CAPACITY_BRANCH if path == CAPACITY_PATH else LEDGER_BRANCH
        url = f"https://api.github.com/repos/{REPOSITORY}/contents/{path}"
        if method == "GET":
            url += "?ref=" + branch
        if payload is not None and payload.get("branch") != branch:
            raise ProbeFailure("store", "wrong-telemetry-branch")
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=self.headers(), method=method)
        return self.json_request(req)

    def read(self, path: str):
        value = self.request("GET", path)
        if value is None:
            return None
        if value.get("encoding") != "base64":
            raise ProbeFailure("store", "unexpected-encoding")
        content = json.loads(base64.b64decode(value["content"]).decode("utf-8"))
        if not isinstance(content, dict) or not value.get("sha"):
            raise ProbeFailure("store", "invalid-telemetry")
        return {"sha": value["sha"], "value": content}

    def create(self, path: str, value: dict) -> None:
        if path == CAPACITY_PATH:
            raise ProbeFailure("store", "capacity-must-use-cas")
        # No sha: Contents API refuses to overwrite an existing immutable path.
        self.request("PUT", path, {
            "message": "Record Site EIC infrastructure capability probe",
            "branch": LEDGER_BRANCH,
            "content": base64.b64encode(json.dumps(value, ensure_ascii=False, indent=2).encode()).decode(),
        })

    def compare_and_swap_capacity(self, expected_sha: str, value: dict) -> bool:
        current = self.read(CAPACITY_PATH)
        if current is None or current["sha"] != expected_sha:
            return False
        try:
            self.request("PUT", CAPACITY_PATH, {
                "message": "Record Site EIC runtime-only capability evidence",
                "branch": CAPACITY_BRANCH,
                "sha": expected_sha,
                "content": base64.b64encode(json.dumps(value, ensure_ascii=False, indent=2).encode()).decode(),
            })
        except ProbeFailure as exc:
            if exc.code in {"http-409", "http-422"}:
                return False
            raise
        return True


def prepare(root: Path, store, state_path: Path) -> dict:
    probe_revision = revision(root)
    if probe_revision != REVIEWED_REVISION:
        return {"claimed": False, "reason": "unreviewed-fallback-revision"}
    if not store.ledger_ready():
        return {"claimed": False, "reason": "isolated-ledger-branch-not-provisioned"}
    capacity = store.read(CAPACITY_PATH)
    if not capacity or capacity["value"].get("status") not in BLOCKED_STATUSES:
        return {"claimed": False, "reason": "capacity-is-not-blocked"}
    if (capacity["value"].get("status") == "LOCAL_FALLBACK_FAILED"
        and capacity["value"].get("capabilityOnly") is not True):
        # Actual producer output rejection is not an infrastructure capability
        # verdict. A synthetic probe must never erase it or grant another trial.
        return {"claimed": False, "reason": "actual-producer-failure-requires-editorial-review"}
    if store.read(claim_path(probe_revision)) is not None:
        return {"claimed": False, "reason": "one-attempt-budget-already-consumed"}
    state = {
        "schemaVersion": 1,
        "owner": "Site Editor-in-Chief",
        "probeRevision": probe_revision,
        "claimedAt": stamp(),
        "attempt": 1,
        "maxAttempts": 1,
        "remainingAttempts": 0,
        "priorCapacity": copy.deepcopy(capacity["value"]),
        "priorCapacitySHA": capacity["sha"],
        "workflowRunId": os.environ.get("GITHUB_RUN_ID"),
        "scope": PROBE_SCOPE,
        "editorialOutcomeVerified": False,
        "publicationPermissionGranted": False,
    }
    store.create(claim_path(probe_revision), state)
    # Only after the immutable claim is accepted may setup/model work begin.
    save_json(state_path, state)
    return {"claimed": True, "reason": "reviewed-revision-budget-claimed", "probeRevision": probe_revision}


def clean_child_env() -> dict[str, str]:
    return {
        key: value for key, value in os.environ.items()
        if not re.search(r"TOKEN|SECRET|PASSWORD|API_KEY", key, re.I)
    }


def run_command(command: list[str], stage: str, deadline: float, *, input_bytes=None, cap=60):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProbeFailure(stage, "runtime-budget-exhausted")
    try:
        result = subprocess.run(
            command,
            input=input_bytes,
            capture_output=True,
            timeout=min(cap, remaining),
            env=clean_child_env(),
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise ProbeFailure(stage, "timeout") from None
    except Exception:
        raise ProbeFailure(stage, "bootstrap-unavailable") from None
    if result.returncode != 0:
        raise ProbeFailure(stage, "command-failed")
    return result.stdout


def local_json(endpoint: str, *, payload=None, timeout=5):
    # Fixed loopback only; ignore proxy env and forbid redirects.
    if endpoint not in {"/api/tags", "/api/generate"}:
        raise ProbeFailure("model", "endpoint-not-allowed")

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            raise ProbeFailure("model", "loopback-redirect-rejected")

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:11434" + endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if payload is None else "POST",
    )
    with opener.open(req, timeout=timeout) as response:
        raw = response.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ProbeFailure("model", "response-too-large")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ProbeFailure("model", "non-object-response")
    return value


def tags_model(tags: dict):
    for row in tags.get("models") or []:
        if isinstance(row, dict) and (row.get("name") or row.get("model")) == MODEL:
            digest = str(row.get("digest") or "")
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ProbeFailure("model", "model-digest-missing")
            return digest
    return None


def bootstrap_runtime(root: Path, deadline: float) -> None:
    run_command(
        [sys.executable, "-m", "pip", "install", "--no-input", "--quiet",
         "--disable-pip-version-check", "--retries", "0", "--timeout", "20",
         "-r", str(root / "scripts/requirements-general-news-fallback.txt")],
        "dependencies", deadline, cap=60,
    )
    if not shutil.which("ollama"):
        installer = run_command(
            ["curl", "-fsSL", "--max-time", "45", "https://ollama.com/install.sh"],
            "model-install-download", deadline, cap=45,
        )
        run_command(["sh"], "model-install", deadline, input_bytes=installer, cap=60)
    try:
        local_json("/api/tags")
        ready = True
    except Exception:
        ready = False
    if not ready:
        # Reuse installer-started daemon; only start one if loopback is not ready.
        subprocess.Popen(
            ["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            env=clean_child_env(),
        )
        for _ in range(20):
            if time.monotonic() >= deadline:
                raise ProbeFailure("model", "runtime-budget-exhausted")
            try:
                local_json("/api/tags", timeout=1)
                ready = True
                break
            except Exception:
                time.sleep(1)
        if not ready:
            raise ProbeFailure("model", "daemon-not-ready")
    if tags_model(local_json("/api/tags")) is None:
        run_command(["ollama", "pull", MODEL], "model-cache", deadline, cap=65)


def check_runtime(root: Path, deadline: float) -> dict:
    # pip may create the user-site directory after this parent interpreter has
    # started. A fresh copy of the same interpreter discovers installed paths;
    # do not import newly installed dependencies using the parent's old sys.path.
    raw = run_command(
        [sys.executable, str(root / REVISION_FILES[2]), "--json-only"],
        "dependencies-check", deadline, cap=20,
    )
    if not isinstance(raw, bytes) or len(raw) > MAX_JSON_BYTES:
        raise ProbeFailure("dependencies-check", "invalid-or-oversized-json")
    def unique_keys(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate-key")
            value[key] = item
        return value
    try:
        versions = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_keys)
    except (UnicodeError, ValueError):
        raise ProbeFailure("dependencies-check", "invalid-json") from None
    if not isinstance(versions, dict) or versions != {"googlenewsdecoder": "0.2.1", "selectolax": "0.4.12"}:
        raise ProbeFailure("dependencies-check", "unexpected-verified-versions")
    digest = tags_model(local_json("/api/tags"))
    if digest is None:
        raise ProbeFailure("model", "model-not-present")
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ProbeFailure("model", "runtime-budget-exhausted")
    response = local_json("/api/generate", payload={
        "model": MODEL,
        "prompt": SYNTHETIC_PROMPT,
        "stream": False,
        "format": "json",
        "keep_alive": 0,
        "options": {"temperature": 0, "num_predict": 40, "num_ctx": 512},
    }, timeout=min(60, remaining))
    if response.get("done") is not True or response.get("model") != MODEL:
        raise ProbeFailure("model", "synthetic-generation-incomplete")
    value = json.loads(str(response.get("response") or ""))
    if value != EXPECTED_SYNTHETIC or type(value.get("value")) is not int:
        raise ProbeFailure("model", "synthetic-contract-failed")
    return {
        "dependencies": versions,
        "model": MODEL,
        "modelDigest": digest,
        "syntheticPromptSHA256": hashlib.sha256(SYNTHETIC_PROMPT.encode()).hexdigest(),
        "syntheticContractPassed": True,
    }


def run_probe(root: Path, state: dict, *, bootstrap=bootstrap_runtime, checker=check_runtime) -> dict:
    result = {
        "schemaVersion": 1, "owner": "Site Editor-in-Chief",
        "probeRevision": state["probeRevision"],
        "checkedAt": stamp(), "attempt": 1, "remainingAttempts": 0,
        "scope": PROBE_SCOPE,
        "status": "LOCAL_FALLBACK_FAILED",
        "editorialOutcomeVerified": False,
        "publicationPermissionGranted": False,
    }
    try:
        if state.get("probeRevision") != REVIEWED_REVISION or revision(root) != REVIEWED_REVISION:
            raise ProbeFailure("revision", "unreviewed-or-changed")
        deadline = time.monotonic() + 260
        bootstrap(root, deadline)
        evidence = checker(root, deadline)
        result["status"] = "LOCAL_FALLBACK_AVAILABLE"
        result["evidence"] = evidence
        result["reason"] = "Reviewed dependency and synthetic local model checks passed; not editorial or publication approval"
        validate_result(result)
    except Exception as exc:
        result["status"] = "LOCAL_FALLBACK_FAILED"
        result.pop("evidence", None)
        result["failure"] = {
            "stage": exc.stage if isinstance(exc, ProbeFailure) else "runtime",
            "code": exc.code if isinstance(exc, ProbeFailure) else type(exc).__name__,
        }
        result["reason"] = "Infrastructure capability probe failed; one-attempt revision budget exhausted"
    result["checkedAt"] = stamp()
    return result


def parse_stamp(value, stage: str) -> datetime:
    if not isinstance(value, str):
        raise ProbeFailure(stage, "invalid-timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        raise ProbeFailure(stage, "invalid-timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ProbeFailure(stage, "timestamp-must-be-utc")
    return parsed


def validate_result(result: dict) -> None:
    if (
        not isinstance(result, dict)
        or type(result.get("schemaVersion")) is not int
        or result.get("schemaVersion") != 1
        or result.get("owner") != "Site Editor-in-Chief"
        or result.get("scope") != PROBE_SCOPE
        or result.get("status") not in {"LOCAL_FALLBACK_AVAILABLE", "LOCAL_FALLBACK_FAILED"}
        or type(result.get("remainingAttempts")) is not int
        or result.get("remainingAttempts") != 0
        or type(result.get("attempt")) is not int
        or result.get("attempt") != 1
        or not isinstance(result.get("reason"), str)
        or not result.get("reason", "").strip()
        or result.get("editorialOutcomeVerified") is not False
        or result.get("publicationPermissionGranted") is not False
    ):
        raise ProbeFailure("finalize", "invalid-runtime-only-result")
    checked_at = parse_stamp(result.get("checkedAt"), "finalize")
    if (checked_at - datetime.now(timezone.utc)).total_seconds() > 5:
        raise ProbeFailure("finalize", "future-result-timestamp")
    if result["status"] == "LOCAL_FALLBACK_AVAILABLE":
        evidence = result.get("evidence") or {}
        if (
            not isinstance(evidence, dict)
            or evidence.get("dependencies") != {"googlenewsdecoder": "0.2.1", "selectolax": "0.4.12"}
            or evidence.get("model") != MODEL
            or not re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("modelDigest") or ""))
            or evidence.get("syntheticContractPassed") is not True
            or evidence.get("syntheticPromptSHA256") != hashlib.sha256(SYNTHETIC_PROMPT.encode()).hexdigest()
        ):
            raise ProbeFailure("finalize", "available-without-exact-runtime-evidence")
    else:
        failure = result.get("failure")
        if (
            not isinstance(failure, dict)
            or any(not isinstance(failure.get(key), str) or not failure[key].strip()
                   for key in ("stage", "code"))
        ):
            raise ProbeFailure("finalize", "failed-without-runtime-failure")


def finalize(store, state: dict, result: dict, capacity_path: Path) -> bool:
    probe_revision = state["probeRevision"]
    if probe_revision != REVIEWED_REVISION or result.get("probeRevision") != probe_revision:
        raise ProbeFailure("finalize", "unreviewed-revision")
    validate_result(result)
    claimed = store.read(claim_path(probe_revision))
    if not claimed or claimed["value"] != state:
        raise ProbeFailure("finalize", "claim-does-not-match")
    if parse_stamp(result["checkedAt"], "finalize") < parse_stamp(state.get("claimedAt"), "finalize"):
        raise ProbeFailure("finalize", "result-predates-claim")
    store.create(result_path(probe_revision), result)
    if (state["priorCapacity"].get("status") == "LOCAL_FALLBACK_FAILED"
        and state["priorCapacity"].get("capabilityOnly") is not True):
        return False
    capacity = copy.deepcopy(state["priorCapacity"])
    # Full old evidence lives in the immutable claim. Do not grow recursive
    # histories in the single current-status object on a future reviewed repair.
    capacity.pop("previousCapacity", None)
    capacity.update({
        "checkedAt": result["checkedAt"],
        "status": result["status"],
        "reason": result["reason"],
        "blockedUntil": None,
        "probeRevision": probe_revision,
        "capabilityOnly": True,
        "editorialOutcomeVerified": False,
        "publicationPermissionGranted": False,
        "remainingProbeAttempts": 0,
        "probeClaimPath": claim_path(probe_revision),
        "probeResultPath": result_path(probe_revision),
        "probeLedgerBranch": LEDGER_BRANCH,
        "localFallbackModel": MODEL,
        "recoveryOwner": "workflow:general-news-producer.yml" if result["status"] == "LOCAL_FALLBACK_AVAILABLE" else state["priorCapacity"].get("recoveryOwner"),
    })
    if not store.compare_and_swap_capacity(state["priorCapacitySHA"], capacity):
        # Do not replay an AVAILABLE result over newer actual producer telemetry.
        return False
    save_json(capacity_path, capacity)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("prepare", "run", "finalize"))
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--state", type=Path, required=True)
    ap.add_argument("--result", type=Path)
    ap.add_argument("--capacity", type=Path)
    ap.add_argument("--github-output", type=Path)
    args = ap.parse_args()
    if args.mode == "run":
        if args.result is None:
            raise SystemExit("--result required")
        result = run_probe(args.root, load_json(args.state))
        save_json(args.result, result)
        print("EIC_CAPABILITY_PROBE_RUNTIME", result["status"], "runtime-only-not-news")
        return 0 if result["status"] == "LOCAL_FALLBACK_AVAILABLE" else 1
    store = GitHubCapacityStore(os.environ.get("GH_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", ""))
    if args.mode == "prepare":
        planned = prepare(args.root, store, args.state)
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as handle:
                handle.write("claimed=" + ("true" if planned["claimed"] else "false") + "\n")
        print("EIC_CAPABILITY_PROBE_PLAN", planned["reason"])
        return 0
    state = load_json(args.state)
    if args.result is None or args.capacity is None:
        raise SystemExit("--result and --capacity required")
    if args.result.is_file():
        result = load_json(args.result)
    else:
        result = {
            "schemaVersion": 1, "owner": "Site Editor-in-Chief",
            "scope": PROBE_SCOPE,
            "probeRevision": state["probeRevision"], "checkedAt": stamp(),
            "status": "LOCAL_FALLBACK_FAILED", "attempt": 1, "remainingAttempts": 0,
            "reason": "Claimed capability probe interrupted or timed out; revision attempt consumed",
            "failure": {"stage": "runtime", "code": "interrupted"},
            "editorialOutcomeVerified": False, "publicationPermissionGranted": False,
        }
    updated = finalize(store, state, result, args.capacity)
    print("EIC_CAPABILITY_PROBE_FINAL", result["status"], "capacity-cas=" + str(updated).lower())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
