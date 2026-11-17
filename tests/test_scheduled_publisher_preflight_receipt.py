from argparse import Namespace
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import scheduled_publisher_preflight_receipt as preflight
from test_scheduled_publication_v9 import fixture


class PreflightTests(unittest.TestCase):
    def test_real_validator_checks_exact_bytes_before_creating_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            draft = root / "draft.json"
            current = root / "current.json"
            receipt = root / "receipt.json"
            data, _ = fixture()
            draft.write_text(json.dumps(data), encoding="utf-8")
            previous = datetime.fromisoformat(data["lastUpdated"]) - timedelta(hours=1)
            current.write_text(json.dumps({"lastUpdated": previous.isoformat()}), encoding="utf-8")
            binding = preflight.fingerprint(draft)
            args = Namespace(
                run="123", attempt="2", validator="a" * 40, candidate="b" * 40,
                draft=draft, receipt=receipt, current_live=current,
                expected=binding["draftSha256"], candidate_blob=binding["candidateBlobSha"],
                base_live=preflight.fingerprint(current)["candidateBlobSha"],
            )
            self.assertEqual(preflight.issue(args), 0)
            self.assertEqual(json.loads(receipt.read_bytes())["runAttempt"], 2)
            receipt.unlink()
            draft.write_bytes(draft.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "bytes do not match"):
                preflight.issue(args)
            self.assertFalse(receipt.exists())

    def test_trust_fails_when_job_or_artifact_is_replayed(self):
        now = datetime.now(timezone.utc)
        run = {
            "id": 123, "run_attempt": 2, "head_sha": "a" * 40, "path": preflight.WORKFLOW,
            "head_branch": "main", "head_repository": {"full_name": preflight.REPO},
            "event": "workflow_dispatch", "conclusion": "success", "status": "completed",
            "created_at": (now - timedelta(minutes=1)).isoformat(), "updated_at": now.isoformat(),
        }
        job = {"name": preflight.JOB, "run_id": 123, "head_sha": "a" * 40, "conclusion": "success"}
        def messages(attempt):
            artifact = io.BytesIO()
            with zipfile.ZipFile(artifact, "w") as archive:
                archive.writestr(preflight.RECEIPT, json.dumps({
                    "schema": preflight.SCHEMA, "repository": preflight.REPO,
                    "workflowRunId": 123, "runAttempt": attempt, "validatorCommitSha": "a" * 40,
                    "candidatePath": preflight.CANDIDATE, "result": "PASS", "checkedAt": now.isoformat(),
                }))
            raw = artifact.getvalue()
            listing = {"total_count": 1, "artifacts": [{
                "id": 456, "name": "scheduled-publisher-preflight-123-2",
                "size_in_bytes": len(raw), "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
            }]}
            return run, {"total_count": 1, "jobs": [job]}, listing, raw
        response = iter(messages(2))
        self.assertEqual(preflight.trusted_receipt("123", now=now, source=lambda *a, **k: next(response))["result"], "PASS")
        response = iter(messages(1))
        with self.assertRaisesRegex(ValueError, "not bound"):
            preflight.trusted_receipt("123", now=now, source=lambda *a, **k: next(response))
        r, jobs, listing, raw = messages(2)
        response = iter((r, jobs, listing, raw[:-1] + bytes([raw[-1] ^ 1])))
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            preflight.trusted_receipt("123", now=now, source=lambda *a, **k: next(response))
        response = iter(messages(2))
        with self.assertRaisesRegex(ValueError, "stale"):
            preflight.trusted_receipt("123", now=now + timedelta(hours=1), source=lambda *a, **k: next(response))

    def test_changed_ref_or_publication_parent_does_not_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.json"
            draft.write_bytes(b'{"candidate":"test-only"}\n')
            receipt = {**preflight.fingerprint(draft), "candidateCommitSha": "b" * 40,
                       "validatorCommitSha": "a" * 40, "baseLiveBlobSha": "c" * 40}
            def blob(path, _ref):
                return receipt["candidateBlobSha"] if path == preflight.CANDIDATE else receipt["baseLiveBlobSha"]
            with patch.object(preflight, "trusted_receipt", return_value=receipt), patch.object(
                preflight, "content_blob", side_effect=blob
            ), patch.object(preflight, "branch_head", return_value="d" * 40):
                with self.assertRaisesRegex(ValueError, "candidate or main changed"):
                    preflight.verify(Namespace(run="123", draft=draft, published_commit=None))
                with patch.object(preflight, "api", return_value={
                    "sha": "d" * 40, "parents": [{"sha": "e" * 40}],
                }):
                    with self.assertRaisesRegex(ValueError, "parent is not"):
                        preflight.verify(Namespace(run="123", draft=draft, published_commit="d" * 40))


if __name__ == "__main__":
    unittest.main()
