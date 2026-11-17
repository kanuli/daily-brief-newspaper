"""Regression tests using simulated GitHub responses; never dispatch a workflow."""
from datetime import datetime, timezone
import hashlib
import io
import json
import unittest
import zipfile

import scheduled_publisher_preflight_receipt as receipt

MAIN = "a" * 40
NOW = datetime(2026, 11, 17, 4, 0, tzinfo=timezone.utc)


def fixture(workflow, *, extra=None):
    run = {
        "id": 12, "run_attempt": 1, "status": "completed", "conclusion": "success",
        "head_branch": "main", "event": "workflow_dispatch", "path": workflow,
        "head_repository": {"full_name": receipt.REPO}, "head_sha": MAIN,
        "created_at": "2026-11-17T03:56:00Z", "updated_at": "2026-11-17T03:59:00Z",
    }
    jobs = [{"name": receipt.JOB, "run_id": 12, "head_sha": MAIN, "conclusion": "success"}]
    if extra:
        jobs.append({"name": extra, "conclusion": "skipped"})
    data = {
        "schema": receipt.SCHEMA, "repository": receipt.REPO, "candidatePath": receipt.CANDIDATE,
        "result": "PASS", "workflowRunId": 12, "runAttempt": 1, "validatorCommitSha": MAIN,
        "checkedAt": "2026-11-17T03:57:00Z",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(receipt.RECEIPT, json.dumps(data))
    raw = buffer.getvalue()
    name = "scheduled-publisher-preflight-12-1"
    listing = {"total_count": 1, "artifacts": [
        {"name": name, "id": 3, "size_in_bytes": len(raw), "digest": "sha256:" + hashlib.sha256(raw).hexdigest()}]}
    responses = {"actions/runs/12": run,
                 "actions/runs/12/attempts/1/jobs?per_page=100": {"jobs": jobs, "total_count": len(jobs)},
                 f"actions/runs/12/artifacts?name={name}&per_page=100": listing,
                 "actions/artifacts/3/zip": raw}
    return lambda endpoint, **kwargs: responses[endpoint]


class IsolatedReceiptTest(unittest.TestCase):
    def test_readback_accepts_dedicated_only_workflow_at_exact_attempt(self):
        value = receipt.trusted_receipt("12", now=NOW, isolated=True, source=fixture(receipt.ISOLATED_WORKFLOW))
        self.assertEqual((value["workflowRunId"], value["runAttempt"], value["validatorCommitSha"]), (12, 1, MAIN))

    def test_isolated_receipt_rejects_original_eic_workflow(self):
        with self.assertRaisesRegex(ValueError, "requested workflow"):
            receipt.trusted_receipt("12", now=NOW, isolated=True, source=fixture(receipt.WORKFLOW))

    def test_isolated_receipt_rejects_an_extra_job_even_if_skipped(self):
        with self.assertRaisesRegex(ValueError, "non-isolated"):
            receipt.trusted_receipt("12", now=NOW, isolated=True,
                                    source=fixture(receipt.ISOLATED_WORKFLOW, extra="assign"))


if __name__ == "__main__":
    unittest.main()
