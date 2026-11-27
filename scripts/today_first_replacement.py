"""Stage the exact reviewed Git site when a separate Pages baseline reset is authorized."""
import hashlib
from pathlib import PurePosixPath
import re
from urllib.error import HTTPError

SITE_DIRS = {"assets", "audio", "data", "editions"}
HEX = re.compile(r"[a-f0-9]{64}\Z")
OID = re.compile(rb"[a-f0-9]{40}\Z")
MAX_FILE = 16 * 1024**2
MAX_SITE = 64 * 1024**2


def require(valid, reason):
    if not valid:
        raise ValueError(reason)


def plan(git, commit, receipt, *, canonical):
    rows = git("ls-tree", "-r", "-z", "--full-tree", commit)
    require(len(rows) < 256 * 1024, "replacement Git tree exceeds bounds")
    output, names = {}, set()
    total = 0
    for row in rows.split(b"\0"):
        if not row:
            continue
        header, raw_name = row.split(b"\t", 1)
        mode, kind, blob = header.split()
        name = raw_name.decode("utf-8", errors="strict")
        parts = name.split("/")
        if parts[0] not in SITE_DIRS and (len(parts) != 1 or PurePosixPath(name).suffix != ".html"):
            continue
        require(name != receipt and len(output) < 1500 and mode == b"100644" and kind == b"blob"
                and OID.fullmatch(blob) and name.casefold() not in names and ":" not in name and "\\" not in name
                and all(part and not part.startswith(".") and all(ord(c) >= 32 and ord(c) != 127 for c in part)
                        for part in parts), "unsafe replacement baseline path")
        names.add(name.casefold())
        oid = blob.decode()
        size = int(git("cat-file", "-s", oid))
        total += size
        require(0 <= size <= MAX_FILE and total <= MAX_SITE, "replacement baseline volume exceeds bounds")
        raw = git("cat-file", "blob", oid)
        git_object = b"blob " + str(size).encode() + b"\0" + raw
        require(size == len(raw) and hashlib.sha1(git_object).digest() == bytes.fromhex(oid),
                "replacement source blob mismatch")
        output[name] = raw
    require(output, "empty replacement site")
    manifest = {k: {"sha256": hashlib.sha256(v).hexdigest(), "bytes":len(v)} for k,v in output.items()}
    return output, hashlib.sha256(canonical(manifest)).hexdigest()


def public_state(read, receipt, tracked_files, *, canonical):
    """Bind the observed public copy and require that it still has no verifiable build receipt."""
    try:
        read(receipt)
    except HTTPError as error:
        if error.code != 404:
            raise ValueError("replacement public receipt unavailable without verified 404") from error
    else:
        raise ValueError("existing Pages receipt requires the normal base path")
    tracked = {name: hashlib.sha256(read(name)).hexdigest() for name in sorted(set(tracked_files))}
    return hashlib.sha256(canonical(tracked)).hexdigest()


def stage(site, git, commit, receipt, *, site_pin, read, tracked_files, public_pin, canonical):
    require(isinstance(site_pin, str) and HEX.fullmatch(site_pin)
            and isinstance(public_pin, str) and HEX.fullmatch(public_pin), "replacement trust pins unavailable")
    require(public_state(read, receipt, tracked_files, canonical=canonical) == public_pin,
            "replacement public snapshot moved")
    output, manifest = plan(git, commit, receipt, canonical=canonical)
    require(manifest == site_pin, "replacement site manifest differs from the separately reviewed pin")
    require(set(tracked_files) <= set(output), "replacement baseline missing served site content")
    for name, raw in output.items():
        path = site / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)
    return manifest
