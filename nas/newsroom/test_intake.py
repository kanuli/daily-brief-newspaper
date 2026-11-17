#!/usr/bin/env python3
"""Offline NAS newsroom intake regressions; no network, Github, or NAS access."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from intake import connect, initialize, ingest, pending, health


def snapshot(*, stamp="2026-11-17T10:20:00+08:00", invalid=False):
    candidate = {
        "id": "news-101", "desk": "hong-kong",
        "title": "本地官方公告核實前候選",
        "url": "https://news.rthk.hk/rthk/ch/component/k2/1878129-20261117.htm",
        "source": "香港電台", "provider": "RTHK Official RSS",
        "publishedAt": "2026-11-17T02:20:00Z",
        "firstSeenAt": stamp, "lastSeenAt": stamp,
    }
    rows = [candidate]
    if invalid:
        rows.append({**candidate, "id": "bad-news", "url": "file:///tmp/fake"})
    return json.dumps({
        "version": 2, "discoveryOnly": True,
        "desks": {"hong-kong": rows, "japan": [{
            "id": "news-202", "desk": "japan",
            "title": "日本企業新聞候選",
            "url": "https://www.jiji.com/jc/article?k=2026111700598&g=soc&m=rss",
            "source": "時事通信", "publishedAt": "2026-11-17T06:30:00Z",
        }]},
    }, ensure_ascii=False).encode("utf-8")


class IntakeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = connect(Path(self.temp.name) / "news.sqlite3")
        initialize(self.conn)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_idempotent_and_unverified(self):
        raw = snapshot()
        first = ingest(self.conn, raw)
        again = ingest(self.conn, raw)
        self.assertEqual(first["admitted"], 2)
        self.assertEqual(again["admitted"], 2)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM candidates").fetchone()[0], 2)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM verification_queue").fetchone()[0], 2)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM intake_runs").fetchone()[0], 1)
        output = pending(self.conn)
        self.assertEqual(output["status"], "UNVERIFIED_EIC_INBOX")
        self.assertFalse(output["publicationAttempted"])
        self.assertEqual(len(output["items"]), 2)
        self.assertNotIn("approved", str(output).lower())

    def test_errors_isolated_and_decisions_preserved(self):
        ingest(self.conn, snapshot())
        self.conn.execute("""UPDATE verification_queue SET state='REJECTED'
                             WHERE desk='japan' AND candidate_id='news-202'""")
        result = ingest(self.conn, snapshot(stamp="2026-11-17T10:30:00+08:00", invalid=True))
        self.assertEqual(result["invalid"], 1)
        self.assertEqual(result["admitted"], 2)
        self.assertEqual(self.conn.execute(
            "SELECT state FROM verification_queue WHERE desk='japan'"
        ).fetchone()[0], "REJECTED")
        self.assertEqual(len(pending(self.conn)["items"]), 1)

    def test_bad_root_cannot_mutate(self):
        with self.assertRaises(ValueError):
            ingest(self.conn, json.dumps({
                "discoveryOnly": False, "desks": {"japan": []},
            }).encode())
        with self.assertRaises(ValueError):
            ingest(self.conn, json.dumps({
                "discoveryOnly": True, "desks": {"unapproved-desk": []},
            }).encode())
        self.assertEqual(self.conn.execute("SELECT count(*) FROM intake_runs").fetchone()[0], 0)

    def test_transaction_rollback(self):
        original = snapshot()
        ingest(self.conn, original)
        invalid_list = {
            "discoveryOnly": True, "desks": {
                "hong-kong": [json.loads(original)["desks"]["hong-kong"][0]],
                "japan": {"invalid": "not a list"},
            },
        }
        with self.assertRaises(ValueError):
            ingest(self.conn, json.dumps(invalid_list).encode())
        self.assertEqual(self.conn.execute("SELECT count(*) FROM intake_runs").fetchone()[0], 1)
        self.assertEqual(health(self.conn)["queue"], {"PENDING_SOURCE_VERIFICATION": 2})
        self.assertFalse(health(self.conn)["nasEicApprovalIntegrated"])
        self.assertFalse(health(self.conn)["phase2SignerAckVerified"])


if __name__ == "__main__":
    unittest.main()
