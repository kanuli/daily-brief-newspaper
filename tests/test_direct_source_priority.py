"""Synthetic candidate ranking only, never source, model or publication calls."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import general_news_verification_robot as robot

NOW = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)


def candidate(number, direct=False):
    return {"id": "synthetic-" + str(number), "desk": "finance",
            "title": "SYNTHETIC ONLY NOT NEWS fixture " + str(number),
            "source": "香港電台" if direct else "Reuters",
            "provider": "RTHK Official RSS" if direct else "Google News RSS",
            "url": "https://news.rthk.hk/rthk/ch/component/k2/1999999-20261009.htm" if direct else "https://example.invalid/" + str(number),
            "publishedAt": "2026-10-09T14:00:00Z", "query": "synthetic-only"}


class DirectSourcePriorityTests(unittest.TestCase):
    def test_verified_feed_locator_is_selected_within_unchanged_four_candidate_cap(self):
        rows = [candidate(i) for i in range(6)] + [candidate(7, direct=True)]
        with patch.object(robot, "soft_stale_desks", return_value=["finance"]), \
             patch.object(robot, "existing_identity", return_value=(set(), set())):
            request = robot.prepare_request({"desks": {"finance": rows}}, {}, {}, NOW)
        self.assertEqual(request["candidateCount"], 4)
        self.assertEqual(request["candidates"][0]["id"], "synthetic-7")
        self.assertNotIn("verifiedCopy", request["candidates"][0])

    def test_provider_label_alone_cannot_grant_the_source_access_preference(self):
        baseline = candidate(7, direct=True)
        expected = robot.candidate_score(baseline)[0]
        for delta in ({"provider": "unreviewed"}, {"source": "unreviewed"},
                      {"desk": "world"}, {"url": "http://127.0.0.1/private"},
                      {"url": "https://news.rthk.hk.evil.invalid/rthk/ch/component/k2/1999999-20261009.htm"}):
            with self.subTest(delta=delta):
                self.assertLess(robot.candidate_score({**baseline, **delta})[0], expected)

    def test_priority_cannot_bypass_current_date_or_duplicate_source_checks(self):
        row = candidate(7, direct=True)
        self.assertFalse(robot.raw_candidate_ok({**row, "publishedAt": "2026-10-07T00:00:00Z"}, "finance", NOW, set(), set()))
        self.assertFalse(robot.raw_candidate_ok(row, "finance", NOW, {row["url"]}, set()))
        self.assertFalse(robot.raw_candidate_ok({**row, "publishedAt": "2026-10-10T14:00:00Z"}, "finance", NOW, set(), set()))


if __name__ == "__main__":
    unittest.main()
