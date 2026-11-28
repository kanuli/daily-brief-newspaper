"""Focused regression checks for structural story contracts and detached coverage."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import build_today_daily_from_desk as daily
from merge_live_into_desk import merge
from publication_coverage import bind_checkpoint, effective_live, validate_editorial
from scheduled_publication_contract import desk_checkpoint_errors
from test_scheduled_publication_v9 import fixture
from validate_daily_v3 import validate_story as validate_daily_story
from validate_editorial_v2 import validate_story as validate_editorial_story
from validate_publication_current import rich_story, validate_live
from validate_voice_currentness import publication_state


def papers():
    now = datetime.now(timezone.utc)
    live, desk = fixture()
    headline = deepcopy(live["items"][0])
    headline["sourceAggregation"] = "AI_GROUP_SOURCE_HEADLINE_V1"
    for field in ("dek", "summary", "body", "context", "why", "watchNext"):
        headline[field] = ""
    return now, live, desk, headline


def projection():
    now, live, desk, headline = papers()
    live["items"][0] = headline
    raw = json.dumps(live, ensure_ascii=False).encode()
    projected, merged = merge(live, desk, now=now)
    return now, live, raw, bind_checkpoint(raw, projected, merged)


class EditorialContracts(unittest.TestCase):
    def test_valid_headline_and_conventional_story(self):
        _, live, _, headline = papers()
        for check in (validate_editorial_story, validate_daily_story, rich_story):
            check(headline, "headline")
            check(live["items"][0], "full")

    def test_conventional_dek_remains_mandatory(self):
        _, live, _, _ = papers()
        broken = dict(live["items"][0], dek="")
        for check in (validate_editorial_story, validate_daily_story, rich_story):
            with self.assertRaisesRegex((ValueError, SystemExit), "missing dek"):
                check(broken, "full")

    def test_headline_cannot_hide_narrative_or_replace_source(self):
        _, _, _, headline = papers()
        altered = [
            dict(headline, body="unapproved narrative"),
            dict(headline, sources=[{"name":"wrong", "url":headline["sourceUrl"]}]),
            dict(headline, timeLabel="invented clock"),
            dict(headline, sourceUrl="http://example.invalid/news"),
            dict(headline, publishedAt="2099-01-01T00:00:00Z"),
            dict(headline, sourceAggregation="made-up-marker"),
        ]
        for variant in altered:
            for check in (validate_editorial_story, validate_daily_story, rich_story):
                with self.assertRaises(ValueError):
                    check(variant, "headline")

    def test_bound_checkpoint_and_original_currentness(self):
        now, live, raw, desk = projection()
        projected = effective_live(raw, desk, now=now)
        self.assertEqual(projected["items"], live["items"])
        self.assertEqual(desk_checkpoint_errors(projected, desk, now=now), [])
        validate_live({"date":live["date"]}, projected, desk, now=now)
        with self.assertRaisesRegex(SystemExit, "independently current Daily"):
            validate_live({"date":"2000-01-01"}, projected, desk, now=now)

    def test_reject_forged_changed_and_stale_checkpoints(self):
        now, _, raw, desk = projection()
        for bad in [{}, {"publicationCheckpoint": []}, dict(desk, generatedAt="1999"),
                    dict(desk, date="1999-02-01")]:
            with self.assertRaisesRegex(ValueError, "MISMATCHED"):
                effective_live(raw, bad, now=now)
        with self.assertRaisesRegex(ValueError, "MISMATCHED"):
            effective_live(raw + b"\n", desk, now=now)
        with self.assertRaisesRegex(ValueError, "UNVERIFIED"):
            effective_live(raw, desk, now=now + timedelta(hours=36))
        desk["publicationCheckpoint"]["coverage"]["footballGateMet"] = False
        with self.assertRaisesRegex(ValueError, "UNVERIFIED"):
            effective_live(raw, desk, now=now)

    def test_daily_and_voice_consume_the_same_pair_read_only(self):
        now, live, raw, desk = projection()
        original_cwd = Path.cwd()
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            live_path = data / "live.json"
            desk_path = data / "desk-latest.json"
            live_path.write_bytes(raw)
            desk_bytes = json.dumps(desk).encode()
            desk_path.write_bytes(desk_bytes)
            (data / "latest.json").write_text('{"date":"2000-01-01"}')
            try:
                os.chdir(root)
                self.assertTrue(publication_state()[0])
                with patch.object(daily, "DATA", data), \
                        patch.object(daily, "desk_checkpoint_errors", wraps=desk_checkpoint_errors) as gate:
                    # Fixture prose need not meet downstream production Daily selection.
                    try:
                        daily.build(now=now)
                    except SystemExit as failure:
                        self.assertNotIn("DAILY_SCHEDULED_LIVE_DESK_CHECKPOINT_HOLD", str(failure))
                    gate.assert_called_once()
                    self.assertEqual(gate.call_args.args[0]["coverage"]["status"], "COMPLETE")
                desk_path.write_text("{}")
                self.assertFalse(publication_state()[0])
                with patch.object(daily, "DATA", data):
                    with self.assertRaisesRegex(SystemExit, "DAILY_SCHEDULED_LIVE_DESK_CHECKPOINT_HOLD"):
                        daily.build(now=now)
                desk_path.write_bytes(desk_bytes)
                with patch("validate_editorial_v2.main", return_value=0):
                    self.assertEqual(validate_editorial(live_path, desk_path), 0)
                self.assertEqual(live_path.read_bytes(), raw)
                self.assertEqual(desk_path.read_bytes(), desk_bytes)
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
