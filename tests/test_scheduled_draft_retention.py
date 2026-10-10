"""Synthetic scheduling fixtures only; no publication, source or model calls."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verified_draft_pending import pending_verified_draft
import newsroom_control_plane as control


def dt(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class ScheduledDraftTests(unittest.TestCase):
    def setUp(self):
        self.draft = {"status": "VERIFIED_DRAFT", "publicationType": "LIVE", "draftId": "synthetic",
                      "createdAt": "2026-10-09T17:21:00Z", "targetPublication": "2026-10-10T06:00:00+08:00",
                      "articles": [{"id": "fixture", "publishedAt": "2026-10-09T14:00:00Z"}]}
        self.now = dt("2026-10-09T20:00:00Z")

    def test_scheduled_overnight_draft_is_not_overwritten_before_six(self):
        self.assertTrue(pending_verified_draft(self.draft, self.now))
        self.assertTrue(control.pending_live_draft(self.draft, self.now))

    def test_due_grace_and_original_ninety_minute_window_are_retained(self):
        for instant in ("2026-10-09T22:08:00Z", "2026-10-09T23:30:00Z"):
            self.assertTrue(pending_verified_draft(self.draft, dt(instant)))
        self.assertFalse(pending_verified_draft(self.draft, dt("2026-10-09T23:30:01Z")))

    def test_consumed_draft_is_never_reserved(self):
        self.assertFalse(pending_verified_draft(self.draft, self.now, {"coverage": {"verifiedDraftId": "synthetic"}}))

    def test_wrong_future_targets_and_missing_identity_fail_closed(self):
        for change in ({"targetPublication": "2026-10-11T06:00:00+08:00"},
                       {"targetPublication": "2026-10-10T06:01:00+08:00"},
                       {"targetPublication": "2026-10-10T06:00:00"}, {"draftId": ""},
                       {"status": "NO_PUBLISHABLE_UPDATE"}, {"articles": []}):
            self.assertFalse(pending_verified_draft({**self.draft, **change}, self.now))

    def test_source_expiry_future_and_missing_date_do_not_get_renewed(self):
        for published in ("2026-10-08T19:59:59Z", "2026-10-09T20:01:00Z", "", "invalid"):
            draft = deepcopy(self.draft)
            draft["articles"][0]["publishedAt"] = published
            self.assertFalse(pending_verified_draft(draft, self.now))

    def test_original_recent_draft_behavior_is_preserved(self):
        draft = {**self.draft, "targetPublication": "invalid"}
        self.assertTrue(pending_verified_draft(draft, dt("2026-10-09T18:00:00Z")))
        self.assertFalse(pending_verified_draft(draft, dt("2026-10-09T17:20:59Z")))

    def test_plain_unscheduled_old_draft_stays_expired(self):
        draft = {**self.draft, "createdAt": "2026-10-09T14:00:00Z"}
        self.assertFalse(pending_verified_draft(draft, self.now))


if __name__ == "__main__":
    unittest.main()
