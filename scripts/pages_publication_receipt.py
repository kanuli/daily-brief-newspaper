"""Bind a built Pages artifact to its checked-out commit and deployed bytes."""
from datetime import date
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


VOCAB = re.compile(r"data/vocab/(?P<date>\d{4}-\d{2}-\d{2}|latest)\.json\Z")


def vocab_stamp(path):
    match = VOCAB.fullmatch(path)
    if match is None:
        raise ValueError(f"unexpected tracked Pages vocabulary path: {path}")
    value = match.group("date")
    if value != "latest":
        date.fromisoformat(value)
    return value


def vocabulary(root, inventory):
    if not 2 <= len(inventory) <= 1500 or "data/vocab/latest.json" not in inventory:
        raise ValueError("Pages vocabulary source inventory missing or outside bounds")
    hashes = {}
    dated = {}
    latest = None
    for path, expected_blob in inventory.items():
        stamp = vocab_stamp(path)
        local = root / path
        if local.is_symlink() or local.parent.is_symlink() or local.parent.parent.is_symlink() or not local.is_file():
            raise ValueError(f"Pages vocabulary source absent or unsafe: {path}")
        with local.open("rb") as f:
            data = f.read(1024 * 1024 + 1)
        if len(data) > 1024 * 1024:
            raise ValueError(f"Pages vocabulary source exceeds size bound: {path}")
        actual_blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        if actual_blob != expected_blob:
            raise ValueError(f"Pages vocabulary differs from checked-out Git source: {path}")
        document = json.loads(data)
        if not isinstance(document, dict) or not isinstance(document.get("words"), list):
            raise ValueError(f"Pages vocabulary invalid JSON schema: {path}")
        source_day = document.get("date")
        hashes[path] = hash_bytes(data)
        if stamp == "latest":
            latest = (source_day, hashes[path])
        elif source_day != stamp:
            raise ValueError(f"Pages vocabulary date does not match path: {path}")
        else:
            dated[stamp] = hashes[path]
    if latest is None or not isinstance(latest[0], str) or dated.get(latest[0]) != latest[1]:
        raise ValueError("Pages vocabulary latest does not match its exact dated source")
    return hashes


def tracked_vocabulary(root, commit):
    result = subprocess.check_output(["git", "ls-tree", "-r", "-z", commit, "--", "data/vocab"],
                                     cwd=root, timeout=10)
    inventory = {}
    for record in result.split(b"\0"):
        if not record:
            continue
        head, raw_name = record.split(b"\t", 1)
        mode, kind, blob = head.decode("ascii").split()
        name = raw_name.decode("ascii")
        if mode != "100644" or kind != "blob" or name in inventory or not re.fullmatch(r"[0-9a-f]{40}", blob):
            raise ValueError(f"unexpected Git Pages vocabulary object: {name}")
        vocab_stamp(name)
        inventory[name] = blob
    return inventory


def build(root, *, commit, run_id, attempt, vocab_inventory=None):
    if not re.fullmatch(r"[0-9a-f]{40}", commit) or not all(
            re.fullmatch(r"[1-9][0-9]*", value) for value in (run_id, attempt)):
        raise ValueError("invalid Pages commit or run identity")
    files = {name: hash_bytes((root / name).read_bytes()) for name in FILES}
    if vocab_inventory is not None:
        files.update(vocabulary(root, vocab_inventory))
    return {"schema": "PUBLICATION_BUILD_RECEIPT_V1" if vocab_inventory is None else "PUBLICATION_BUILD_RECEIPT_V2",
            "sourceCommit": commit, "runId": run_id, "runAttempt": attempt, "files": files}


def verify(remote_get, expected):
    remote = json.loads(remote_get(RECEIPT))
    if remote != expected:
        raise ValueError("public Pages build receipt mismatch")
    files = set(expected.get("files", {}))
    schema = expected.get("schema")
    extra = files - set(FILES)
    if schema == "PUBLICATION_BUILD_RECEIPT_V2":
        if not set(FILES) <= files or not 2 <= len(extra) <= 1500 or "data/vocab/latest.json" not in extra:
            raise ValueError("public Pages vocabulary receipt inventory invalid")
        for path in extra:
            vocab_stamp(path)
    elif schema != "PUBLICATION_BUILD_RECEIPT_V1" or files != set(FILES):
        raise ValueError("public Pages receipt schema or inventory mismatch")
    for name, digest in expected["files"].items():
        if hash_bytes(remote_get(name)) != digest:
            raise ValueError(f"public Pages content hash mismatch: {name}")


def main():
    root = Path.cwd()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True, timeout=10).strip()
    receipt = build(root, commit=commit, run_id=os.environ["GITHUB_RUN_ID"],
                    attempt=os.environ["GITHUB_RUN_ATTEMPT"], vocab_inventory=tracked_vocabulary(root, commit))
    from atomic_publish import atomic_write_json
    atomic_write_json(root / RECEIPT, receipt)
    print("PAGES_BUILD_RECEIPT", commit, receipt["runId"], receipt["runAttempt"])


if __name__ == "__main__":
    main()
