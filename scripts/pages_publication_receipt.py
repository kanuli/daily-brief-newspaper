"""Bind a built Pages artifact to its checked-out commit and deployed bytes."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

RECEIPT = "data/publication-build-receipt.json"
FILES = ("data/live.json", "data/desk-latest.json", "data/latest.json",
         "index.html", "live.html", "world.html", "asia.html", "hong-kong.html",
         "japan.html", "finance.html", "technology.html", "manga-anime.html",
         "manchester-united.html", "football.html", "archive.html")


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def build(root, *, commit, run_id, attempt):
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not all(
            re.fullmatch(r"[1-9][0-9]*", value) for value in (run_id, attempt)):
        raise ValueError("invalid Pages commit or run identity")
    return {"schema": "PUBLICATION_BUILD_RECEIPT_V1", "sourceCommit": commit,
            "runId": run_id, "runAttempt": attempt,
            "files": {name: hash_bytes((root / name).read_bytes()) for name in FILES}}


def verify(remote_get, expected):
    remote = json.loads(remote_get(RECEIPT))
    if remote != expected or set(remote.get("files", {})) != set(FILES):
        raise ValueError("public Pages build receipt mismatch")
    for name, digest in expected["files"].items():
        if hash_bytes(remote_get(name)) != digest:
            raise ValueError(f"public Pages content hash mismatch: {name}")


def main():
    root = Path.cwd()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10).strip()
    receipt = build(root, commit=commit, run_id=os.environ["GITHUB_RUN_ID"],
                    attempt=os.environ["GITHUB_RUN_ATTEMPT"])
    from atomic_publish import atomic_write_json
    atomic_write_json(root / RECEIPT, receipt)
    print("PAGES_BUILD_RECEIPT", commit, receipt["runId"], receipt["runAttempt"])


if __name__ == "__main__":
    main()
