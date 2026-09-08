#!/usr/bin/env python3
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
DESK = ROOT / "data" / "desk-latest.json"
FLOORS = {
    "world": 8,
    "asia": 8,
    "hong-kong": 6,
    "japan": 8,
    "market-economy": 8,
    "ai-tech": 6,
    "manga-anime": 4,
    "manchester-united": 4,
    "football": 10,
}


def unique_count(items):
    seen = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        ident = str(item.get("id") or "").strip()
        if not ident:
            ident = "title:" + " ".join(str(item.get("title") or "").split()).lower()
        if ident:
            seen.add(ident)
    return len(seen)


def parse_and_counts(raw):
    data = json.loads(raw)
    desks = data.get("desks") if isinstance(data, dict) else None
    if not isinstance(desks, dict):
        raise ValueError("missing desks object")
    counts = {slug: unique_count(desks.get(slug)) for slug in FLOORS}
    return data, counts


def healthy(counts):
    return all(counts.get(slug, 0) >= floor for slug, floor in FLOORS.items())


def current_state():
    try:
        raw = DESK.read_text(encoding="utf-8")
        _, counts = parse_and_counts(raw)
        return raw, counts
    except Exception:
        return None, {slug: 0 for slug in FLOORS}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8")


def main():
    raw, counts = current_state()
    if raw is not None and healthy(counts):
        print("ROLLING_DESK_CONTAINER_HEALTHY", counts)
        return

    print("ROLLING_DESK_CONTAINER_RECOVERY_REQUIRED", counts)
    commits = [x.strip() for x in git("rev-list", "--all", "--", "data/desk-latest.json").splitlines() if x.strip()]
    for commit in commits:
        try:
            candidate = git("show", f"{commit}:data/desk-latest.json")
            _, candidate_counts = parse_and_counts(candidate)
        except Exception:
            continue
        if not healthy(candidate_counts):
            continue
        DESK.write_text(candidate.rstrip() + "\n", encoding="utf-8")
        print("ROLLING_DESK_CONTAINER_RESTORED", commit, candidate_counts)
        return

    raise SystemExit("No historical Rolling Desk snapshot satisfies all hard floors; refusing empty-container repair")


if __name__ == "__main__":
    main()
