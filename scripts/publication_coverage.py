"""Resolve Rolling Desk coverage against the exact immutable Live bytes."""
from hashlib import sha256
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from atomic_publish import atomic_write_json
from scheduled_publication_contract import is_scheduled

FIELD = "publicationCheckpoint"
SCHEMA = "AI_GROUP_FORMAL_DESK_CHECKPOINT_V1"


def semantic_sha(document):
    raw = json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    return sha256(raw).hexdigest()


def _without(document, field):
    return {key: value for key, value in document.items() if key != field}


def bind_checkpoint(raw, projected, desk):
    live = json.loads(raw)
    if not is_scheduled(live):
        return None
    if (_without(live, "coverage") != _without(projected, "coverage")
            or desk.get("generatedAt") != live.get("lastUpdated") or desk.get("date") != live.get("date")
            or not isinstance(projected.get("coverage"), dict)):
        raise ValueError("FORMAL_DESK_INPUT_CHANGED")
    body = _without(desk, FIELD)
    packet = {"schema": SCHEMA, "liveSha256": sha256(raw).hexdigest(), "deskSha256": semantic_sha(body),
              "generatedAt": desk["generatedAt"], "coverage": projected["coverage"]}
    return {**body, FIELD: packet}


def effective_live(raw, desk, *, now=None):
    live = json.loads(raw)
    if not is_scheduled(live):
        return live
    if not isinstance(desk, dict):
        raise ValueError("FORMAL_DESK_CHECKPOINT_MISSING_STALE_OR_MISMATCHED")
    packet = desk.get(FIELD)
    body = _without(desk, FIELD)
    if (not isinstance(packet, dict)
            or set(packet) != {"schema", "liveSha256", "deskSha256", "generatedAt", "coverage"}
            or packet["schema"] != SCHEMA or packet["liveSha256"] != sha256(raw).hexdigest()
            or packet["deskSha256"] != semantic_sha(body) or packet["generatedAt"] != desk.get("generatedAt")
            or packet["generatedAt"] != live.get("lastUpdated") or desk.get("date") != live.get("date")
            or not isinstance(packet["coverage"], dict)):
        raise ValueError("FORMAL_DESK_CHECKPOINT_MISSING_STALE_OR_MISMATCHED")
    from merge_live_into_desk import live_coverage_diagnostics

    if packet["coverage"] != live_coverage_diagnostics(live, body, now=now):
        raise ValueError("FORMAL_DESK_COVERAGE_UNVERIFIED_OR_CHANGED")
    return {**live, "coverage": packet["coverage"]}


def publication_input(live_path, desk_path, *, now=None):
    """Read one bound pair. No changes are made to either input."""
    raw = live_path.read_bytes()
    desk = json.loads(desk_path.read_bytes())
    return effective_live(raw, desk, now=now), desk


def validate_editorial(live_path, desk_path):
    """Run the original editorial checks on an isolated in-memory-derived projection."""
    import validate_editorial_v2 as validator

    raw = live_path.read_bytes()
    if not is_scheduled(json.loads(raw)):
        return validator.main()
    desk = json.loads(desk_path.read_bytes())
    projection = effective_live(raw, desk)
    with TemporaryDirectory(prefix="formal-editorial-qa-") as staging:
        previous = validator.DATA
        validator.DATA = Path(staging)
        try:
            atomic_write_json(validator.DATA / "live.json", projection)
            atomic_write_json(validator.DATA / "desk-latest.json", desk)
            return validator.main()
        finally:
            validator.DATA = previous


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("original_live", type=Path, nargs="?")
    cli.add_argument("--validate-editorial", action="store_true")
    args = cli.parse_args()
    if args.validate_editorial == (args.original_live is not None):
        cli.error("choose the original Live path or --validate-editorial")
    live, desk = Path("data/live.json"), Path("data/desk-latest.json")
    if args.validate_editorial:
        return validate_editorial(live, desk)
    raw = args.original_live.read_bytes()
    bound = bind_checkpoint(raw, json.loads(live.read_bytes()), json.loads(desk.read_bytes()))
    if bound is not None:
        atomic_write_json(desk, bound)
        live.write_bytes(raw)


if __name__ == "__main__":
    raise SystemExit(main())
