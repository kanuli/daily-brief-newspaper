#!/usr/bin/env python3
"""NAS-local newsroom intake and Phase-2 verification queue.

This program NEVER approves stories, dispatches robots, updates GitHub, or
publishes anything. Its input is discovery data, not source verification.
All write operations are scoped to an explicitly supplied local SQLite path.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

DESKS = frozenset((
    "world", "asia", "hong-kong", "japan", "finance", "stock-news",
    "ai-tech", "manga-anime", "manchester-united", "football",
))
MAX_SNAPSHOT_BYTES = 8_000_000
MAX_ROWS_PER_DESK = 500
MAX_QUEUE_RESULT = 200
SCHEMA = "NAS_NEWSROOM_INTAKE_V1"
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,159}$")


def stamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return result.astimezone(timezone.utc) if result.utcoffset() is not None else None


def direct_url(value: object) -> bool:
    if not isinstance(value, str) or any(c.isspace() for c in value):
        return False
    try:
        part = urlsplit(value)
        return part.scheme == "https" and bool(part.hostname) and not (
            part.username or part.password
        )
    except ValueError:
        return False


def connect(db: Path) -> sqlite3.Connection:
    # The caller supplies a NAS *local* filesystem path, not an SMB/NFS mount.
    db = db.expanduser().resolve()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA foreign_keys=ON")
    mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]
    if mode.lower() != "wal":
        raise RuntimeError("WAL could not be enabled on this database path")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


def initialize(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS candidates (
            desk TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source TEXT NOT NULL,
            provider TEXT NOT NULL,
            published_at TEXT,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            raw_json TEXT NOT NULL,
            PRIMARY KEY (desk, candidate_id)
        );
        CREATE INDEX IF NOT EXISTS candidates_seen
            ON candidates(last_seen);
        CREATE TABLE IF NOT EXISTS verification_queue (
            desk TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'PENDING_SOURCE_VERIFICATION'
                CHECK(state IN ('PENDING_SOURCE_VERIFICATION', 'CLAIMED',
                                'SOURCE_VERIFIED', 'REJECTED')),
            attempt INTEGER NOT NULL DEFAULT 0,
            leased_until TEXT,
            owner TEXT,
            review_evidence_id TEXT,
            PRIMARY KEY (desk, candidate_id),
            FOREIGN KEY (desk, candidate_id)
                REFERENCES candidates(desk, candidate_id)
        );
        CREATE TABLE IF NOT EXISTS intake_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checked_at TEXT NOT NULL,
            snapshot_sha256 TEXT NOT NULL UNIQUE,
            admitted INTEGER NOT NULL,
            invalid INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS latest_snapshot (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            raw_json TEXT NOT NULL,
            sha256 TEXT NOT NULL,
            recorded_at TEXT NOT NULL
        );
    """)


def valid_row(desk: str, item: object) -> bool:
    if not isinstance(item, dict):
        return False
    identifier = item.get("id")
    if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier):
        return False
    if item.get("desk") != desk:
        return False
    if not direct_url(item.get("url")):
        return False
    if not isinstance(item.get("title"), str) or not item["title"].strip():
        return False
    if not isinstance(item.get("source"), str) or not item["source"].strip():
        return False
    if item.get("publishedAt") not in (None, "") and stamp(item["publishedAt"]) is None:
        return False
    return True


def ingest(conn: sqlite3.Connection, raw: bytes) -> dict:
    if not raw or len(raw) > MAX_SNAPSHOT_BYTES:
        raise ValueError("invalid snapshot size")
    snapshot = json.loads(raw)
    if not isinstance(snapshot, dict) or snapshot.get("discoveryOnly") is not True:
        raise ValueError("not a discovery-only staging snapshot")
    desks = snapshot.get("desks")
    if not isinstance(desks, dict) or not desks:
        raise ValueError("missing discovery desks")
    if set(desks) - DESKS:
        raise ValueError("unknown desk in snapshot")
    checked_at = datetime.now(timezone.utc).isoformat()
    sha = hashlib.sha256(raw).hexdigest()
    admitted = 0
    invalid = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for desk, items in desks.items():
            if not isinstance(items, list) or len(items) > MAX_ROWS_PER_DESK:
                raise ValueError("invalid desk candidate list")
            for item in items:
                if not valid_row(desk, item):
                    invalid += 1
                    continue
                identifier = item["id"]
                # Preserve real publisher timestamps as received. Arrival is
                # a separate timestamp and is never source verification.
                first_seen = item.get("firstSeenAt") or checked_at
                last_seen = item.get("lastSeenAt") or checked_at
                if stamp(first_seen) is None or stamp(last_seen) is None:
                    invalid += 1
                    continue
                published = item.get("publishedAt") or None
                conn.execute("""
                    INSERT INTO candidates(
                        desk,candidate_id,title,url,source,provider,
                        published_at,first_seen,last_seen,raw_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(desk,candidate_id) DO UPDATE SET
                        title=excluded.title, url=excluded.url,
                        source=excluded.source, provider=excluded.provider,
                        published_at=excluded.published_at,
                        last_seen=excluded.last_seen,
                        raw_json=excluded.raw_json
                """, (
                    desk, identifier, item["title"].strip(), item["url"],
                    item["source"].strip(), str(item.get("provider") or ""),
                    published, first_seen, last_seen,
                    json.dumps(item, ensure_ascii=False, sort_keys=True),
                ))
                # A subsequent discovery cycle must never overwrite an
                # EIC/robot queue decision or re-admit a rejected candidate.
                conn.execute("""
                    INSERT OR IGNORE INTO verification_queue(desk,candidate_id)
                    VALUES (?,?)
                """, (desk, identifier))
                admitted += 1
        conn.execute("""
            INSERT OR IGNORE INTO intake_runs(
                checked_at,snapshot_sha256,admitted,invalid
            ) VALUES(?,?,?,?)
        """, (checked_at, sha, admitted, invalid))
        conn.execute("""
            INSERT INTO latest_snapshot(singleton,raw_json,sha256,recorded_at)
            VALUES (1,?,?,?)
            ON CONFLICT(singleton) DO UPDATE SET raw_json=excluded.raw_json,
                sha256=excluded.sha256,recorded_at=excluded.recorded_at
        """, (raw.decode("utf-8"), sha, checked_at))
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    return {"schema": SCHEMA, "result": "INGESTED_DISCOVERY_ONLY",
            "admitted": admitted, "invalid": invalid, "snapshotSha256": sha,
            "publicationAttempted": False}


def pending(conn: sqlite3.Connection, limit: int = 50) -> dict:
    if not 1 <= limit <= MAX_QUEUE_RESULT:
        raise ValueError("invalid queue limit")
    rows = conn.execute("""
        SELECT c.desk,c.candidate_id,c.title,c.url,c.source,c.provider,
               c.published_at,c.first_seen,c.last_seen
        FROM verification_queue AS q
        JOIN candidates AS c USING (desk,candidate_id)
        WHERE q.state='PENDING_SOURCE_VERIFICATION'
        ORDER BY c.last_seen DESC, c.desk, c.candidate_id
        LIMIT ?
    """, (limit,)).fetchall()
    # This is an untrusted EIC intake view. It is NOT an approved publisher feed.
    return {"schema": SCHEMA, "status": "UNVERIFIED_EIC_INBOX",
            "items": [dict(x) for x in rows], "publicationAttempted": False}


def health(conn: sqlite3.Connection) -> dict:
    rows = conn.execute("""
        SELECT state,COUNT(*) AS total FROM verification_queue GROUP BY state
    """).fetchall()
    last = conn.execute("""
        SELECT checked_at,admitted,invalid FROM intake_runs
        ORDER BY id DESC LIMIT 1
    """).fetchone()
    return {"schema": SCHEMA, "queue": {r["state"]: r["total"] for r in rows},
            "lastIntake": dict(last) if last else None,
            "publicationAttempted": False, "nasEicApprovalIntegrated": False,
            "phase2SignerAckVerified": False}


def collect_local(conn: sqlite3.Connection, repo: Path, mode: str) -> dict:
    repo = repo.expanduser().resolve()
    collector = repo / "scripts" / "rolling_news_collector.py"
    if not collector.is_file():
        raise FileNotFoundError("existing collector missing from repository")
    with tempfile.TemporaryDirectory(prefix="nas-news-intake-") as work:
        prior = Path(work) / "previous.json"
        new = Path(work) / "snapshot.json"
        previous = conn.execute(
            "SELECT raw_json FROM latest_snapshot WHERE singleton=1"
        ).fetchone()
        args = [sys.executable, "-B", str(collector), "--output", str(new),
                "--mode", mode]
        if previous:
            prior.write_text(previous["raw_json"], encoding="utf-8")
            args.extend(("--existing", str(prior)))
        # No GitHub tokens, no workflow calls, no writes to the checked-out repo.
        result = subprocess.run(args, cwd=str(repo), capture_output=True,
                                text=True, timeout=300, check=False)
        if result.returncode != 0 or not new.is_file():
            raise RuntimeError("collector failed; existing DB state preserved: "
                               + (result.stderr or result.stdout)[-350:])
        return ingest(conn, new.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", required=True, type=Path,
                        help="SQLite file on NAS local filesystem (not SMB/NFS)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    entry = sub.add_parser("ingest")
    entry.add_argument("--snapshot", type=Path, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--repo", type=Path, required=True)
    collect.add_argument("--mode", choices=("normal", "deep"), default="normal")
    queue = sub.add_parser("inbox")
    queue.add_argument("--limit", type=int, default=50)
    sub.add_parser("health")
    args = parser.parse_args()
    try:
        with connect(args.db) as conn:
            initialize(conn)
            if args.command == "init":
                output = {"schema": SCHEMA, "result": "INITIALIZED",
                          "publicationAttempted": False}
            elif args.command == "ingest":
                output = ingest(conn, args.snapshot.read_bytes())
            elif args.command == "collect":
                output = collect_local(conn, args.repo, args.mode)
            elif args.command == "inbox":
                output = pending(conn, args.limit)
            else:
                output = health(conn)
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error,
            subprocess.SubprocessError, json.JSONDecodeError) as exc:
        print(f"NAS_NEWSROOM_INTAKE_HOLD {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
