"""Build a reviewed Pages bootstrap baseline from exact, known public bytes."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import PurePosixPath
import re
from urllib.error import HTTPError

from today_first_replacement import HEX, MAX_FILE, MAX_SITE, SITE_DIRS, require

SCHEMA = "PUBLIC_PAGES_BASELINE_V1"
VOCAB_PATH = re.compile(r"data/vocab/\d{4}-\d{2}-\d{2}\.json\Z")
MAX_PATHS = 1500


def digest(raw):
    return sha256(raw).hexdigest()


def safe(name):
    pieces = name.split("/")
    return (name.isascii() and len(name) <= 240
            and all(re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", part) for part in pieces)
            and (pieces[0] in SITE_DIRS or len(pieces) == 1 and PurePosixPath(name).suffix == ".html"))


def reviewed(raw, *, sha_pin, commit, repo, receipt, required, parse):
    require(0 < len(raw) <= 256 * 1024 and HEX.fullmatch(sha_pin) and digest(raw) == sha_pin,
            "public baseline does not match the reviewed manifest pin")
    value = parse(raw)
    require(isinstance(value, dict) and set(value) == {"schema", "repository", "reviewCommit", "files", "absent"},
            "invalid public baseline manifest schema")
    require(value["schema"] == SCHEMA and value["repository"] == repo and value["reviewCommit"] == commit,
            "public baseline manifest repository or review commit differs")
    files, absent = value["files"], value["absent"]
    require(isinstance(files, dict) and isinstance(absent, list) and len(files) + len(absent) <= MAX_PATHS
            and set(required) <= files.keys() and receipt in absent and not files.keys() & set(absent),
            "public baseline inventory incomplete")
    paths = list(files) + absent
    require(all(isinstance(name, str) and safe(name) for name in paths)
            and len({name.casefold() for name in paths}) == len(paths)
            and all(name == receipt or VOCAB_PATH.fullmatch(name) for name in absent),
            "unsafe or ambiguous public baseline inventory")
    total = 0
    for descriptor in files.values():
        require(isinstance(descriptor, dict) and set(descriptor) == {"sha256", "size"}
                and isinstance(descriptor["sha256"], str) and HEX.fullmatch(descriptor["sha256"])
                and type(descriptor["size"]) is int and 0 < descriptor["size"] <= MAX_FILE,
                "invalid public baseline file descriptor")
        total += descriptor["size"]
    require(total <= MAX_SITE, "public baseline exceeds size bound")
    return value


def checked_public(plan, read, *, output=None, paths=None, absent=None):
    """Verify reviewed bytes before writing. Pre-deploy callers can verify without writing."""
    files = plan["files"] if paths is None else paths
    missing = plan["absent"] if absent is None else absent

    def check(name):
        expected = files[name]
        raw = read(name)
        require(len(raw) == expected["size"] and digest(raw) == expected["sha256"],
                f"public baseline bytes differ: {name}")
        if output is not None:
            target = output / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(raw)

    def confirm_absence(name):
        try:
            read(name)
        except HTTPError as error:
            if error.code == 404:
                return
            raise ValueError(f"public baseline absence unverified: {name}") from error
        raise ValueError(f"public baseline path appeared: {name}")

    with ThreadPoolExecutor(max_workers=6) as workers:
        for _ in workers.map(confirm_absence, missing):
            pass
        for _ in workers.map(check, sorted(files)):
            pass
