"""Issue and verify binding for the existing Scheduled Publisher draft.

The verifier uses GitHub's run, job, artifact and Git object records. A PASS
receipt establishes bytes and freshness, never editorial or write authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import zipfile

REPO = "kanuli/daily-brief-newspaper"
WORKFLOW = ".github/workflows/editor-in-chief-newsroom-assignment.yml"
JOB = "scheduled-publisher-preflight"
CANDIDATE = "data/scheduled-live-candidate.json"
LIVE = "data/live.json"
RECEIPT = "scheduled-publisher-preflight.json"
SCHEMA = "SCHEDULED_PUBLISHER_PREFLIGHT_V1"
MAX_DRAFT = 1_048_576
MAX_RECEIPT = 4096
AGE = timedelta(minutes=20)


def need(condition, code):
    if not condition:
        raise ValueError(code)


def sha(value, size=40):
    need(isinstance(value, str) and re.fullmatch(rf"[0-9a-f]{{{size}}}", value),
         "invalid SHA")
    return value


def positive_id(value):
    need(isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,18}", value),
         "invalid run or attempt ID")
    return value


def fingerprint(path):
    with path.open("rb") as stream:
        raw = stream.read(MAX_DRAFT + 1)
    need(0 < len(raw) <= MAX_DRAFT, "draft size outside bounds")
    return {
        "draftSha256": hashlib.sha256(raw).hexdigest(),
        "candidateBlobSha": hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest(),
        "draftBytes": len(raw),
    }


def stamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    need(result.utcoffset() is not None, "receipt clock has no timezone")
    return result


def issue(args):
    run, attempt = map(positive_id, (args.run, args.attempt))
    receipt = {
        "schema": SCHEMA,
        "repository": REPO,
        "workflowRunId": int(run),
        "runAttempt": int(attempt),
        "validatorCommitSha": sha(args.validator),
        "candidateCommitSha": sha(args.candidate),
        "baseLiveBlobSha": sha(args.base_live),
        "candidatePath": CANDIDATE,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        **fingerprint(args.draft),
        "result": "HOLD",
    }
    need(receipt["draftSha256"] == sha(args.expected, 64), "draft bytes do not match submitted SHA-256")
    need(receipt["candidateBlobSha"] == sha(args.candidate_blob), "draft bytes do not match candidate blob")
    # Prevent a byte-exact replay of an older Live as well as stale branch tips.
    draft = json.loads(args.draft.read_bytes())
    prior = json.loads(args.current_live.read_bytes())
    need(fingerprint(args.current_live)["candidateBlobSha"] == receipt["baseLiveBlobSha"],
         "base Live bytes do not match the checkout")
    from scheduled_publication_contract import stamp as publication_stamp
    need(publication_stamp(draft.get("lastUpdated")) > publication_stamp(prior.get("lastUpdated")),
         "candidate does not advance the current Live clock")
    validator = Path(__file__).with_name("scheduled_publication_contract.py")
    for extra in ([], ["--merge-commit", args.validator]):
        proc = subprocess.run([sys.executable, "-B", str(validator), str(args.draft), *extra], timeout=60)
        if proc.returncode:
            break
    else:
        receipt["result"] = "PASS"
    with args.receipt.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=True, sort_keys=True)
        stream.write("\n")
    return 0 if receipt["result"] == "PASS" else 1


def api(path, *, binary=False):
    result = subprocess.run(
        ["gh", "api", "--method", "GET", f"repos/{REPO}/{path}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25, check=True,
    ).stdout
    return result if binary else json.loads(result)


def branch_head(branch):
    return sha(api(f"git/ref/heads/{branch}")["object"]["sha"])


def content_blob(path, ref):
    sha(ref)
    record = api(f"contents/{path}?ref={ref}")
    need(record.get("type") == "file" and record.get("path") == path,
         "bound path is not a file")
    return sha(record["sha"])


def trusted_receipt(run_id, *, now, source=api):
    positive_id(run_id)
    run = source(f"actions/runs/{run_id}")
    need(run.get("id") == int(run_id) and run.get("status") == "completed"
         and run.get("conclusion") == "success" and run.get("head_branch") == "main"
         and run.get("event") == "workflow_dispatch" and run.get("path") == WORKFLOW
         and (run.get("head_repository") or {}).get("full_name") == REPO,
         "run is not a successful main EIC preflight")
    attempt = positive_id(str(run.get("run_attempt")))
    job_rows = source(f"actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100")
    jobs = job_rows["jobs"]
    need(job_rows["total_count"] == len(jobs) and len(jobs) <= 100,
         "incomplete attempt jobs")
    preflight = [job for job in jobs if job.get("name") == JOB and job.get("conclusion") == "success"]
    need(len(preflight) == 1 and preflight[0].get("run_id") == int(run_id)
         and preflight[0].get("head_sha") == run.get("head_sha")
         and not any(job.get("name") == "assign" and job.get("conclusion") != "skipped"
                     for job in jobs), "missing or non-isolated preflight job")
    name = f"scheduled-publisher-preflight-{run_id}-{attempt}"
    listing = source(f"actions/runs/{run_id}/artifacts?name={name}&per_page=100")
    matching = [row for row in listing["artifacts"] if row.get("name") == name and not row.get("expired")]
    need(listing["total_count"] == 1 and len(matching) == 1, "receipt artifact missing or ambiguous")
    artifact = matching[0]
    artifact_id = positive_id(str(artifact.get("id")))
    need(type(artifact.get("size_in_bytes")) is int and 0 < artifact["size_in_bytes"] <= MAX_RECEIPT,
         "receipt artifact outside bounds")
    digest = artifact.get("digest", "")
    need(isinstance(digest, str) and digest.startswith("sha256:"), "receipt artifact digest missing")
    expected = sha(digest.removeprefix("sha256:"), 64)
    raw = source(f"actions/artifacts/{artifact_id}/zip", binary=True)
    need(len(raw) == artifact["size_in_bytes"] and
         hashlib.sha256(raw).hexdigest() == expected, "receipt artifact digest mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        need(len(entries) == 1 and entries[0].filename == RECEIPT
             and 0 < entries[0].file_size <= MAX_RECEIPT, "unexpected receipt archive entry")
        receipt = json.loads(archive.read(entries[0]))
    need(receipt.get("schema") == SCHEMA and receipt.get("repository") == REPO
         and receipt.get("candidatePath") == CANDIDATE and receipt.get("result") == "PASS"
         and receipt.get("workflowRunId") == int(run_id) and receipt.get("runAttempt") == int(attempt)
         and sha(receipt.get("validatorCommitSha")) == sha(run.get("head_sha")),
         "receipt not bound to the successful run attempt")
    checked = stamp(receipt["checkedAt"])
    need(stamp(run["created_at"]) <= checked <= stamp(run["updated_at"])
         and timedelta(0) <= now - checked <= AGE, "stale or inconsistent receipt")
    return receipt


def verify(args):
    receipt = trusted_receipt(args.run, now=datetime.now(timezone.utc))
    need(all(receipt.get(k) == v for k, v in fingerprint(args.draft).items()),
         "local draft bytes do not match preflight")
    candidate = sha(receipt["candidateCommitSha"])
    base = sha(receipt["validatorCommitSha"])
    live_blob = sha(receipt["baseLiveBlobSha"])
    need(content_blob(CANDIDATE, candidate) == receipt["candidateBlobSha"]
         and content_blob(LIVE, base) == live_blob, "receipt Git objects do not match")
    main = branch_head("main")
    if args.published_commit:
        commit_id = sha(args.published_commit)
        commit = api(f"git/commits/{commit_id}")
        need(commit.get("sha") == commit_id and [x["sha"] for x in commit["parents"]] == [base],
             "publication parent is not the approved base")
        if main != commit_id:
            comparison = api(f"compare/{commit_id}...{main}?per_page=1")
            need(comparison.get("merge_base_commit", {}).get("sha") == commit_id,
                 "publication commit is not on main")
        need(content_blob(LIVE, commit_id) == receipt["candidateBlobSha"],
             "published Live bytes do not match receipt")
        result = "PUBLISHED_BYTES_VERIFIED"
    else:
        need(branch_head("prepublish-news") == candidate and main == base,
             "candidate or main changed; rerun authorized preflight")
        result = "DRAFT_BYTES_VERIFIED_FOR_EXISTING_PUBLISHER"
    print(json.dumps({**receipt, "verification": result}, sort_keys=True))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    issue_parser = sub.add_parser("issue")
    issue_parser.add_argument("draft", type=Path)
    issue_parser.add_argument("receipt", type=Path)
    issue_parser.add_argument("--current-live", type=Path, required=True)
    for field in ("run", "attempt", "validator", "candidate", "candidate-blob", "expected", "base-live"):
        issue_parser.add_argument("--" + field, required=True)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("run")
    verify_parser.add_argument("draft", type=Path)
    verify_parser.add_argument("--published-commit")
    args = parser.parse_args()
    try:
        return issue(args) if args.command == "issue" else verify(args)
    except (ValueError, KeyError, TypeError, OSError, zipfile.BadZipFile, subprocess.SubprocessError, AttributeError) as exc:
        print(f"SCHEDULED_PREFLIGHT_HOLD {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
