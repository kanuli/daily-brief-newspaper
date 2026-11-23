"""Stage exact Publisher bytes and request the existing read-only EIC preflight."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import base64
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import scheduled_publication_contract as contract
import scheduled_publisher_preflight_receipt as receipt

BRANCH = "prepublish-news"
WORKFLOW = receipt.ISOLATED_WORKFLOW.rsplit("/", 1)[1]
API_VERSION = "2026-03-10"
TRANSPORT_ERRORS = (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError)


def gh(method, endpoint, body):
    raw = subprocess.run(
        ["gh", "api", "--hostname", "github.com", "--method", method, endpoint,
         "-H", f"X-GitHub-Api-Version: {API_VERSION}", "--input", "-"],
        input=json.dumps(body).encode(), capture_output=True, timeout=35, check=True,
    ).stdout
    return json.loads(raw)


def draft_bytes(path):
    with path.open("rb") as stream:
        raw = stream.read(receipt.MAX_DRAFT + 1)
    receipt.need(0 < len(raw) <= receipt.MAX_DRAFT, "draft size outside bounds")
    return raw


def check_live(raw, validator):
    # Validate the captured bytes with the deployed CLI without modifying its
    # source (that path automatically triggers the privileged EIC workflow).
    with TemporaryDirectory() as directory:
        frozen = Path(directory) / "draft.json"
        frozen.write_bytes(raw)
        command = [sys.executable, "-B", str(Path(contract.__file__).resolve()), str(frozen)]
        result = subprocess.run(command, capture_output=True, timeout=30, check=False)
        if result.returncode:
            detail = (result.stderr or result.stdout).decode("utf-8", errors="replace").strip()[:600]
            raise ValueError("local contract rejected: " + detail)
        result = subprocess.run([*command, "--merge-commit", validator], capture_output=True,
                                timeout=30, check=False)
        merge = json.loads(result.stdout)
        receipt.need(result.returncode == 0 and merge["status"] == "PASS",
                     "local Merge gate rejected: " + "; ".join(merge["errors"][:8]))
    draft = json.loads(raw)
    live = receipt.api(f"contents/{receipt.LIVE}?ref={validator}")
    receipt.need(live.get("type") == "file" and live.get("encoding") == "base64",
                 "could not inspect pinned base Live")
    prior = json.loads(base64.b64decode(live["content"]))
    receipt.need(contract.stamp(draft.get("lastUpdated")) > contract.stamp(prior.get("lastUpdated")),
                 "draft does not advance pinned Live")


def check_live_only(raw, validator, *, now=None):
    """Prepare a Live-only handoff from exact bytes, without requesting a Merge or deployment."""
    from today_first_live import candidate_live
    draft = candidate_live(raw, now=now or datetime.now(timezone.utc))
    live = receipt.api(f"contents/{receipt.LIVE}?ref={validator}")
    receipt.need(live.get("type") == "file" and live.get("encoding") == "base64",
                 "could not inspect pinned base Live")
    prior = json.loads(base64.b64decode(live["content"]))
    receipt.need(contract.stamp(draft["lastUpdated"]) > contract.stamp(prior.get("lastUpdated")),
                 "draft does not advance pinned Live")


def check_current_validator(pinned, *, live_only=False):
    receipt.need(receipt.branch_head("main") == pinned, "main changed; review the new validator")
    paths = [Path(contract.__file__), Path(receipt.__file__)]
    if live_only:
        here = Path(__file__).resolve().parent
        paths.extend(here / f"{name}.py" for name in ("today_first_live", "editorial_draft",
                                                     "scheduled_publisher_handoff",
                                                     "merge_live_into_desk", "emit_verified_live"))
    for local in paths:
        receipt.need(receipt.fingerprint(local)["candidateBlobSha"] ==
                     receipt.content_blob(f"scripts/{local.name}", pinned),
                     f"local {local.name} differs from deployed source")


def candidate_blob_at(commit):
    obj = receipt.api(f"git/commits/{commit}")
    receipt.need(obj["sha"] == commit, "candidate commit metadata mismatch")
    root = receipt.api(f"git/trees/{receipt.sha(obj['tree']['sha'])}")
    receipt.need(root.get("truncated") is False, "candidate root tree truncated")
    data = [e for e in root["tree"] if e["path"] == "data"]
    receipt.need(len(data) == 1 and data[0]["type"] == "tree", "candidate data tree missing")
    tree = receipt.api(f"git/trees/{receipt.sha(data[0]['sha'])}")
    receipt.need(tree.get("truncated") is False, "candidate data tree truncated")
    found = [e for e in tree["tree"] if e["path"] == receipt.CANDIDATE.rsplit("/", 1)[1]]
    if not found:
        return None
    receipt.need(len(found) == 1 and found[0]["mode"] == "100644", "candidate is not a regular file")
    return receipt.sha(found[0]["sha"])


def stage(raw, parent, blob):
    receipt.need(receipt.branch_head(BRANCH) == parent, "candidate branch changed before staging")
    if candidate_blob_at(parent) == blob:
        receipt.need(receipt.branch_head(BRANCH) == parent, "candidate branch moved during no-op")
        return parent
    payload = {
        "query": "mutation($input:CreateCommitOnBranchInput!) {createCommitOnBranch(input:$input){commit{oid}}}",
        "variables": {"input": {
            "branch": {"repositoryNameWithOwner": receipt.REPO, "branchName": BRANCH},
            "expectedHeadOid": parent,
            "message": {"headline": "Stage existing Scheduled Publisher candidate"},
            "fileChanges": {"additions": [{"path": receipt.CANDIDATE, "contents": base64.b64encode(raw).decode()}]},
        }},
    }
    try:
        message = gh("POST", "graphql", payload)
        response = receipt.sha(message["data"]["createCommitOnBranch"]["commit"]["oid"])
    except TRANSPORT_ERRORS:
        # No second mutation. Recover only if readback proves the exact change.
        response = None
    tip = receipt.branch_head(BRANCH)
    receipt.need(tip != parent and (response is None or response == tip),
                 "staging denied, ambiguous, or superseded; no mutation retried")
    comparison = receipt.api(f"compare/{parent}...{tip}?per_page=2")
    files = comparison["files"]
    receipt.need(comparison.get("total_commits") == 1 and comparison["status"] == "ahead"
                 and comparison["merge_base_commit"]["sha"] == parent and len(files) == 1
                 and files[0]["filename"] == receipt.CANDIDATE
                 and files[0]["status"] in ("added", "modified")
                 and candidate_blob_at(tip) == blob,
                 "staged commit was not the single expected candidate addition or update")
    receipt.need(receipt.branch_head(BRANCH) == tip, "staged candidate superseded")
    return tip


def dispatch(parent, validator, draft_hash, journal):
    workflow = receipt.api(f"actions/workflows/{WORKFLOW}")
    receipt.need(workflow.get("path") == receipt.ISOLATED_WORKFLOW and workflow.get("state") == "active",
                 "dedicated workflow is not active")
    receipt.need(receipt.branch_head(BRANCH) == parent and receipt.branch_head("main") == validator,
                 "repository moved before dispatch")
    reservation = journal / f"{validator}-{parent}.json"
    try:
        with reservation.open("x", encoding="utf-8") as file:
            json.dump({"candidateCommitSha": parent, "validatorCommitSha": validator,
                       "draftSha256": draft_hash, "status": "DISPATCH_RESERVED"}, file)
            file.flush()
            os.fsync(file.fileno())
    except FileExistsError:
        raise ValueError("dispatch already reserved; inspect existing GitHub run and verify it") from None
    try:
        result = gh("POST", f"repos/{receipt.REPO}/actions/workflows/{WORKFLOW}/dispatches",
                    {"ref": "main", "inputs": {"scheduled_candidate_commit": parent,
                                               "scheduled_draft_sha256": draft_hash,
                                               "reviewed_validator_commit": validator}})
        run = receipt.positive_id(str(result["workflow_run_id"]))
    except TRANSPORT_ERRORS:
        raise ValueError("dispatch result unknown or denied; reservation retained; inspect Actions") from None
    with reservation.with_suffix(".run").open("x", encoding="ascii") as file:
        file.write(run + "\n")
        file.flush()
        os.fsync(file.fileno())
    return run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("inspect", "stage", "dispatch", "verify"))
    parser.add_argument("draft", type=Path)
    parser.add_argument("--validator", required=True, help="reviewed deployed main SHA")
    parser.add_argument("--expected-tip", required=True, help="expected prepublish-news SHA")
    parser.add_argument("--draft-sha256", required=True, help="exact SHA-256 from existing Publisher")
    parser.add_argument("--publication-scope", choices=("full", "live"), default="full")
    parser.add_argument("--run", help="exact run ID returned by Actions")
    parser.add_argument("--journal", type=Path, help="existing private dispatch journal directory")
    args = parser.parse_args()
    try:
        validator, tip = map(receipt.sha, (args.validator, args.expected_tip))
        raw = draft_bytes(args.draft)
        draft_hash = hashlib.sha256(raw).hexdigest()
        receipt.need(draft_hash == receipt.sha(args.draft_sha256, 64), "Publisher draft bytes changed")
        blob = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
        if args.publication_scope == "live":
            receipt.need(args.step in ("inspect", "stage"), "LIVE_PAGES_WORKFLOW_REQUIRED")
            check_current_validator(validator, live_only=True)
            check_live_only(raw, validator)
        else:
            check_current_validator(validator)
            check_live(raw, validator)
        receipt.need(receipt.branch_head(BRANCH) == tip, "candidate branch tip changed")
        result = {"candidateBlobSha": blob, "candidateCommitSha": tip,
                  "validatorCommitSha": validator, "draftSha256": draft_hash, "status": "INSPECTED"}
        if args.publication_scope == "live":
            result["publicationScope"] = "live"
        if args.step == "stage":
            result.update(candidateCommitSha=stage(raw, tip, blob), status="STAGED")
        elif args.step in ("dispatch", "verify"):
            receipt.need(candidate_blob_at(tip) == blob, "stage exact draft before preflight")
            if args.step == "dispatch":
                receipt.need(args.journal is not None and args.journal.is_dir()
                             and not args.journal.is_symlink(), "private journal directory required")
                result.update(workflowRunId=dispatch(tip, validator, draft_hash, args.journal),
                              status="DISPATCHED_NOT_VERIFIED")
            else:
                receipt.need(args.run is not None, "exact workflow --run required")
                output = io.StringIO()
                # Verify the same bytes even if the input file changes while reading GitHub.
                with TemporaryDirectory() as directory, redirect_stdout(output):
                    frozen = Path(directory) / "draft.json"
                    frozen.write_bytes(raw)
                    receipt.verify(argparse.Namespace(run=args.run, draft=frozen, published_commit=None,
                                                       isolated=True))
                checked = json.loads(output.getvalue())
                receipt.need(all(checked.get(k) == v for k, v in result.items() if k != "status")
                             and checked.get("draftBytes") == len(raw), "run receipt did not match handoff")
                print(output.getvalue(), end="")
                return 0
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, TypeError, KeyError, AttributeError, OSError, subprocess.SubprocessError) as exc:
        print(f"PUBLISHER_HANDOFF_HOLD {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
