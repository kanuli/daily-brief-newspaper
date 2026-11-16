"""Publish one validated checkpoint using ordinary fast-forward Git updates."""
import argparse
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import time


INPUTS = (
    "data/live.json", "data/desk-latest.json", "data/latest.json",
    "scripts/", "config/", ".github/workflows/",
)


class CheckpointHold(Exception):
    """The candidate must be rebuilt against an updated newsroom checkout."""


def push_checkpoint(cwd, *, pause=time.sleep, verify_only=False):
    def git(*args, check=True):
        return subprocess.run(["git", *args], cwd=cwd, check=check,
                              stdout=subprocess.PIPE, timeout=20)

    def unchanged(left, right, paths):
        result = git("diff", "--quiet", left, right, "--", *paths, check=False)
        if result.returncode not in (0, 1):
            result.check_returncode()
        return result.returncode == 0

    def fetch_tip():
        git("fetch", "--no-tags", "origin", "refs/heads/main")
        return git("rev-parse", "FETCH_HEAD").stdout.strip().decode("ascii")

    def contains_checkpoint(remote, checkpoint):
        result = git("merge-base", "--is-ancestor", checkpoint, remote, check=False)
        if result.returncode not in (0, 1):
            result.check_returncode()
        return result.returncode == 0

    checkpoint = git("rev-parse", "HEAD").stdout.strip().decode("ascii")
    base = git("rev-parse", "HEAD^").stdout.strip().decode("ascii")
    changed = git("diff", "--no-renames", "--name-only", "-z", base, checkpoint).stdout
    updates = tuple(part.decode("utf-8") for part in changed.split(bytes(1)) if part)
    paths = (*INPUTS, *updates)
    if "data/latest.json" in updates:
        try:
            edition = json.loads(git("show", f"{checkpoint}:data/latest.json").stdout)
            day = edition["date"]
            if date.fromisoformat(day).isoformat() != day:
                raise ValueError("Daily date must be canonical ISO")
        except (KeyError, TypeError, ValueError, subprocess.SubprocessError) as exc:
            raise CheckpointHold("PUBLICATION_CHECKPOINT_DAILY_PROVENANCE_HOLD") from exc
        paths = (*paths, f"data/{day}.json")
    for attempt in range(5):
        try:
            remote = fetch_tip()
            confirmed = contains_checkpoint(remote, checkpoint)
        except (OSError, subprocess.SubprocessError) as exc:
            if not verify_only:
                raise
            raise CheckpointHold("PUBLICATION_CHECKPOINT_PUSH_UNVERIFIED_HOLD") from exc
        if confirmed:
            if not unchanged(checkpoint, remote, paths):
                raise CheckpointHold("PUBLICATION_CHECKPOINT_SUPERSEDED_HOLD")
            return "ALREADY_PUBLISHED"
        if verify_only:
            raise CheckpointHold("PUBLICATION_CHECKPOINT_PUSH_UNVERIFIED_HOLD")

        if (git("merge-base", "--is-ancestor", base, remote, check=False).returncode != 0
                or not unchanged(base, remote, paths)):
            raise CheckpointHold("PUBLICATION_CHECKPOINT_STALE_INPUT_HOLD")

        if remote != base:
            git("rebase", remote)
            base = remote
            checkpoint = git("rev-parse", "HEAD").stdout.strip().decode("ascii")
        try:
            result = git("push", "origin", "HEAD:refs/heads/main", check=False)
        except subprocess.TimeoutExpired:
            # The branch may have advanced even though the response was lost.
            result = None
        if result is not None and result.returncode == 0:
            # A successful push may already have been superseded before dispatch.
            try:
                published = fetch_tip()
                confirmed = contains_checkpoint(published, checkpoint)
                stable = confirmed and unchanged(checkpoint, published, paths)
            except (OSError, subprocess.SubprocessError) as exc:
                raise CheckpointHold("PUBLICATION_CHECKPOINT_PUSH_UNVERIFIED_HOLD") from exc
            if not confirmed:
                raise CheckpointHold("PUBLICATION_CHECKPOINT_PUSH_UNVERIFIED_HOLD")
            if not stable:
                raise CheckpointHold("PUBLICATION_CHECKPOINT_SUPERSEDED_HOLD")
            return "PUBLISHED"
        if attempt < 4:
            pause(2 * (attempt + 1))
    raise CheckpointHold("PUBLICATION_CHECKPOINT_PUSH_UNVERIFIED_HOLD")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true", help="Recheck the remote without pushing")
    args = parser.parse_args()
    try:
        status = push_checkpoint(Path.cwd(), verify_only=args.verify_only)
    except CheckpointHold as exc:
        sys.exit(str(exc))
    print("PUBLICATION_CHECKPOINT", status)
