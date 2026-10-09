#!/usr/bin/env python3
"""One EIC child, three bounded workers; never publication or budget authority.

Private workflow artifacts are input/output transport only. The unchanged
canonical merge and producer are still the only route to a verified draft.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

WORKERS = 3
PROBES_PER_WORKER = 4
CALLS_PER_WORKER = 1
MODEL = "gemma3:4b-it-qat"


def read(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("object-required")
    return value


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def partition(request, index):
    if type(index) is not int or not 0 <= index < WORKERS:
        raise ValueError("invalid-worker")
    desks = request.get("staleDesks")
    rows = request.get("candidates")
    if (not isinstance(desks, list) or not all(isinstance(x, str) and x for x in desks)
        or len(set(desks)) != len(desks) or not isinstance(rows, list)):
        raise ValueError("invalid-request")
    ids = set()
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"]
            or row["id"] in ids or row.get("desk") not in desks):
            raise ValueError("ambiguous-candidate")
        ids.add(row["id"])
    assigned = desks[index::WORKERS]
    return {**request, "staleDesks": assigned,
            "candidates": [row for row in rows if row["desk"] in assigned],
            "candidateCount": sum(row["desk"] in assigned for row in rows)}


def check_plan(plan, request, staging, state, run_id, code_sha, now, *, generation=False):
    if (type(plan.get("schemaVersion")) is not int or plan["schemaVersion"] != 1 or plan.get("runId") != run_id
        or plan.get("codeSHA") != code_sha or not re.fullmatch(r"[0-9a-f]{40}", code_sha)
        or plan.get("requestDigest") != digest(request) or plan.get("stagingDigest") != digest(staging)
        or plan.get("stateDigest") != digest(state) or plan.get("workerCount") != WORKERS
        or plan.get("maxSourceProbesPerWorker") != PROBES_PER_WORKER
        or type(plan.get("maxModelCallsPerWorker")) is not int or plan["maxModelCallsPerWorker"] != CALLS_PER_WORKER
        or type(plan.get("active")) is not bool):
        raise ValueError("plan-binding-invalid")
    created, absolute, deadline = (plan.get(key) for key in ("createdUnix", "absoluteDeadlineUnix", "deadlineUnix"))
    if (any(type(x) not in (int, float) or not math.isfinite(x) for x in (created, absolute, deadline))
        or created > now or not created < deadline <= min(absolute, created + 600)
        or absolute - created > 660 or now - created > 1200):
        raise ValueError("plan-clock-invalid")
    if generation and now >= deadline:
        raise ValueError("shared-deadline-expired")
    for index in range(WORKERS):
        partition(request, index)
    if plan["active"]:
        from editorial_revision_trial import CONTRACT_REVISION, parse_stamp
        if (not isinstance(state, dict) or state.get("claim", {}).get("contractRevision") != CONTRACT_REVISION
            or state.get("run", {}).get("childRunId") != run_id
            or absolute != parse_stamp(state["run"]["boundAt"], "parallel").timestamp() + 660):
            raise ValueError("trial-deadline-or-child-invalid")
    elif state is not None:
        raise ValueError("unexpected-trial-state")


def collect(plan, request, fragments):
    verified, articles, seen = [], [], set()
    if len(fragments) > WORKERS:
        raise ValueError("too-many-fragments")
    for fragment in fragments:
        index = fragment.get("worker")
        if type(index) is not int or index in seen or not 0 <= index < WORKERS:
            raise ValueError("duplicate-or-invalid-worker")
        seen.add(index)
        if (fragment.get("planDigest") != digest(plan) or fragment.get("model") != MODEL
            or type(fragment.get("ok")) is not bool):
            raise ValueError("fragment-not-bound")
        if not fragment["ok"]:
            if fragment.get("facts") is not None or fragment.get("copies") is not None:
                raise ValueError("failed-worker-with-copy")
            continue
        facts, copies = fragment.get("facts"), fragment.get("copies")
        if not isinstance(facts, dict) or not isinstance(copies, dict):
            raise ValueError("missing-fragment-payload")
        fv, ca = facts.get("verified"), copies.get("articles")
        if not isinstance(fv, list) or not isinstance(ca, list) or len(fv) != 1 or len(ca) != 1:
            raise ValueError("worker-exceeds-one-model-call")
        assigned = {row["id"]: row for row in partition(request, index)["candidates"]}
        if (not isinstance(fv[0], dict) or not isinstance(ca[0], dict)
            or fv[0].get("candidateId") not in assigned
            or ca[0].get("candidateId") != fv[0]["candidateId"]
            or fv[0].get("desk") != assigned[fv[0]["candidateId"]]["desk"]):
            raise ValueError("unassigned-worker-candidate")
        verified.extend(fv)
        articles.extend(ca)
    return {"verified": verified}, {"articles": articles}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=("plan", "authorize", "restore", "worker", "collect"))
    ap.add_argument("--directory", type=Path, required=True)
    ap.add_argument("--root", type=Path, default=Path("."))
    ap.add_argument("--deadline-unix", type=float)
    ap.add_argument("--active", choices=("true", "false"))
    ap.add_argument("--worker", type=int)
    ap.add_argument("--fragments", type=Path)
    ap.add_argument("--github-output", type=Path)
    args = ap.parse_args()
    import editorial_revision_trial as trial
    child = trial.context("child")
    if not trial.reviewed_code(args.root):
        raise ValueError("unreviewed-worker-code")
    code = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.root, text=True).strip()
    directory = args.directory
    request, staging = read(directory / "request.json"), read(directory / "staging.json")
    state = read(directory / "state.json") if (directory / "state.json").is_file() else None
    now = time.time()
    if args.mode == "plan":
        plan = {"schemaVersion": 1, "runId": child["runId"], "codeSHA": code,
                "requestDigest": digest(request), "stagingDigest": digest(staging), "stateDigest": digest(state),
                "createdUnix": now, "absoluteDeadlineUnix": args.deadline_unix,
                "deadlineUnix": min(args.deadline_unix, now + 600), "active": args.active == "true",
                "workerCount": WORKERS, "maxSourceProbesPerWorker": PROBES_PER_WORKER,
                "maxModelCallsPerWorker": CALLS_PER_WORKER}
        check_plan(plan, request, staging, state, child["runId"], code, now)
        write(directory / "plan.json", plan)
        return 0
    plan = read(directory / "plan.json")
    check_plan(plan, request, staging, state, child["runId"], code, now,
               generation=args.mode in {"authorize", "worker"})
    if args.mode in {"authorize", "restore"}:
        if plan["active"] != (args.active == "true"):
            raise ValueError("active-owner-output-mismatch")
        if plan["active"]:
            store = trial.TrialStore(os.environ.get("GH_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", ""))
            trial.verify_state(args.root, store, state, child, trial.now_utc())
        with args.github_output.open("a", encoding="utf-8") as handle:
            handle.write("deadline_unix=" + str(plan["deadlineUnix"]) + "\n")
            handle.write("active=" + str(plan["active"]).lower() + "\n")
        return 0
    if args.mode == "worker":
        subset = partition(request, args.worker)
        # Read-only authorization happened in the preceding trusted step.
        # Neither model nor source code receives repository credentials.
        for key in list(os.environ):
            if any(word in key.upper() for word in ("TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "API_KEY")):
                os.environ.pop(key, None)
        import general_news_local_fallback as fallback
        fallback.MAX_SOURCE_PROBES = PROBES_PER_WORKER
        fallback.MAX_MODEL_CALLS = CALLS_PER_WORKER
        write(directory / "worker-request.json", subset)
        sys.argv = ["general_news_local_fallback.py", str(directory / "worker-request.json"),
                    "--facts", str(directory / "facts.raw"), "--copies", str(directory / "copy.raw"),
                    "--deadline-unix", str(plan["deadlineUnix"]), "--daily-ready-copy"]
        ok = False
        try:
            ok = fallback.main() == 0
        except (SystemExit, Exception) as exc:
            print("PARALLEL_WORKER_FAILED type=" + type(exc).__name__, flush=True)
        fragment = {"worker": args.worker, "planDigest": digest(plan), "model": MODEL, "ok": ok,
                    "facts": read(directory / "facts.raw") if ok else None,
                    "copies": read(directory / "copy.raw") if ok else None}
        collect(plan, request, [fragment])
        write(directory / "fragment.json", fragment)
        print(f"PARALLEL_WORKER_RESULT worker={args.worker} ok={str(ok).lower()}", flush=True)
        return 0 if ok else 1
    # Collection never interprets a worker flag as permission to publish.
    if plan["active"]:
        store = trial.TrialStore(os.environ.get("GH_TOKEN", ""), os.environ.get("GITHUB_REPOSITORY", ""))
        trial.verify_state(args.root, store, state, child, trial.now_utc())
    fragments = []
    for index in range(WORKERS):
        path = args.fragments / f"gemma-worker-{index}" / "fragment.json"
        if path.is_file():
            fragment = read(path)
            if fragment.get("worker") != index:
                raise ValueError("artifact-worker-mismatch")
            fragments.append(fragment)
    facts, copies = collect(plan, request, fragments)
    write(directory / "facts.raw", facts)
    write(directory / "copy.raw", copies)
    with args.github_output.open("a", encoding="utf-8") as handle:
        handle.write("ok=" + str(bool(copies["articles"])).lower() + "\n")
    print(f"PARALLEL_COLLECTION accepted={len(copies['articles'])} fragments={len(fragments)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print("PARALLEL_FALLBACK_REJECTED type=" + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1) from None
