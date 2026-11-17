import base64
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main
from unittest.mock import patch

import scheduled_publisher_handoff as handoff

BASE, NEXT, MAIN, BLOB = (char * 40 for char in "abcd")
DRAFT = b'{"exact":"bytes"}\r\n'
DIGEST = "a" * 64
ISOLATED = {"path": handoff.receipt.ISOLATED_WORKFLOW, "state": "active"}


class HandoffTests(TestCase):
    def test_stage_recovers_single_exact_commit_when_response_lost(self):
        comparison = {"total_commits": 1, "status": "ahead", "merge_base_commit": {"sha": BASE},
                      "files": [{"filename": handoff.receipt.CANDIDATE, "status": "added"}]}
        with patch.object(handoff.receipt, "branch_head", side_effect=[BASE, NEXT, NEXT]), \
             patch.object(handoff, "candidate_blob_at", side_effect=[None, BLOB]), \
             patch.object(handoff.receipt, "api", return_value=comparison), \
             patch.object(handoff, "gh", side_effect=TimeoutError) as mutation:
            self.assertEqual(handoff.stage(DRAFT, BASE, BLOB), NEXT)
        args = mutation.call_args.args
        self.assertEqual(args[:2], ("POST", "graphql"))
        request = args[2]["variables"]["input"]
        self.assertEqual(request["expectedHeadOid"], BASE)
        self.assertEqual(request["branch"]["branchName"], "prepublish-news")
        entry, = request["fileChanges"]["additions"]
        self.assertEqual(base64.b64decode(entry["contents"]), DRAFT)

    def test_superseded_tip_does_not_send_mutation(self):
        with patch.object(handoff.receipt, "branch_head", return_value=NEXT), \
             patch.object(handoff, "gh") as mutation:
            with self.assertRaisesRegex(ValueError, "branch changed"):
                handoff.stage(DRAFT, BASE, BLOB)
        mutation.assert_not_called()

    def test_lost_dispatch_response_persists_reservation_and_does_not_retry(self):
        with TemporaryDirectory() as tmp, patch.object(handoff.receipt, "branch_head",
                                                        side_effect=[BASE, MAIN] * 2), \
             patch.object(handoff.receipt, "api", return_value=ISOLATED), \
             patch.object(handoff, "gh", side_effect=TimeoutError) as post:
            for marker in ("result unknown", "already reserved"):
                with self.assertRaisesRegex(ValueError, marker):
                    handoff.dispatch(BASE, MAIN, DIGEST, Path(tmp))
            self.assertEqual(len(list(Path(tmp).glob("*.json"))), 1)
        post.assert_called_once()
        self.assertIn("scheduled-publisher-readonly-preflight.yml/dispatches", post.call_args.args[1])
        self.assertEqual(post.call_args.args[2], {"ref": "main", "inputs": {
            "scheduled_candidate_commit": BASE, "scheduled_draft_sha256": DIGEST,
            "reviewed_validator_commit": MAIN}})

    def test_dispatch_returns_only_exact_run_id_and_journals_it(self):
        with TemporaryDirectory() as tmp, patch.object(handoff.receipt, "branch_head",
                                                        side_effect=[BASE, MAIN]), \
             patch.object(handoff.receipt, "api", return_value=ISOLATED), \
             patch.object(handoff, "gh", return_value={"workflow_run_id": 150}):
            self.assertEqual(handoff.dispatch(BASE, MAIN, DIGEST, Path(tmp)), "150")
            self.assertEqual(next(Path(tmp).glob("*.run")).read_text(), "150\n")

    def test_legacy_workflow_cannot_be_used_as_a_dispatch_fallback(self):
        with TemporaryDirectory() as tmp, patch.object(handoff.receipt, "api", return_value={
                 "path": handoff.receipt.WORKFLOW, "state": "active"}), \
             patch.object(handoff, "gh") as post:
            with self.assertRaisesRegex(ValueError, "dedicated workflow is not active"):
                handoff.dispatch(BASE, MAIN, DIGEST, Path(tmp))
            self.assertFalse(list(Path(tmp).iterdir()))
        post.assert_not_called()

    def test_malformed_contract_rejected_before_contacting_github(self):
        with patch.object(handoff.receipt, "api") as remote:
            with self.assertRaisesRegex(ValueError, "publicationContract must be"):
                handoff.check_live(DRAFT, MAIN)
        remote.assert_not_called()

if __name__ == "__main__":
    main()
