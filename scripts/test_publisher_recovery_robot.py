"""Exercise the registered EIC inline entry point with persisted telemetry."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

from publisher_recovery_robot import (
    CATALOGUE, DISPATCHER, REPOSITORY, authorize, execute, read, require_eic_run, record_eic_review,
)


REGISTRY = read(CATALOGUE.with_name("newsroom-robots.json"))
CAT = read(CATALOGUE)
SHA = "a" * 40


def cycle(now, *, issue=True):
    result = {"role": "Editor-in-Chief", "dispatcher": DISPATCHER, "checkedAt": now.isoformat(),
              "cycleId": now.isoformat(), "assignments": [], "healthy": not issue,
              "evidenceSnapshot": {"publicationValidatorOk": not issue}}
    if issue:
        result["evidenceSnapshot"]["staleDesks"] = ["world"]
        result["assignments"].append({"robot": "general-producer", "requiresExternalPublisher": True})
    return result


class RobotTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 14, 16, tzinfo=timezone.utc)

    def test_eic_authority_and_branch_scope(self):
        with self.assertRaisesRegex(ValueError, "EIC_RUN_SCOPE_HOLD"):
            require_eic_run({"GITHUB_ACTIONS": "true"})
        with self.assertRaisesRegex(ValueError, "EIC_ASSIGNMENT_SCOPE_HOLD"):
            authorize(REGISTRY, dict(cycle(self.now), role="CTO"), self.now)
        with self.assertRaisesRegex(ValueError, "EIC_ASSIGNMENT_SCOPE_HOLD"):
            authorize(REGISTRY, cycle(self.now-timedelta(minutes=13)), self.now)

    def test_persistence_budget_and_currentness(self):
        attempts = []
        def scan():
            attempts.append(1)
            return {"general-news-producer.yml": {"updated_at": self.now.isoformat(), "conclusion": "failure",
                    "jobs": [{"failed_steps": ["Fail non-capacity verification/copy errors"]}]}}
        args = (REGISTRY, CAT, cycle(self.now))
        first = execute(*args, {}, {}, {}, {}, {}, SHA, now=self.now, receipt_reader=scan)
        self.assertEqual(first["outcome"], "HOLD")
        self.assertIn("PRODUCER_SOURCE_OR_COPY_STAGE_FAILED", first["reasonCodes"])
        self.assertEqual(first["externalPublisherReceipt"], "NOT_VERIFIED")
        state = json.loads(json.dumps({"publisherRecoveryRobot": first, "publisherRecoveryAudit": [first]}))
        self.assertEqual(first, execute(*args, {}, {}, {}, {}, state, SHA, now=self.now, receipt_reader=scan))
        self.assertEqual(attempts, [1])
        later = self.now+timedelta(minutes=16)
        live = {"lastUpdated": later.isoformat()}
        desk = {"generatedAt": later.isoformat()}
        pages = dict(sourceCommit=SHA, checkedAt=later.isoformat(), observedLiveAt=later.isoformat(),
                     observedDeskAt=later.isoformat(), publicationCurrentness={"current": True},
                     probeRunId=78, probeRunAttempt=2,
                     publicationRecoveryVerified=True, liveMatch=True, deskMatch=True, dailyMatch=True,
                     match=True, publicationComplete=True)
        healthy = cycle(later, issue=False)
        rejected = execute(REGISTRY, CAT, healthy, {}, live, desk, dict(pages, sourceCommit="b"*40),
                           state, SHA, now=later)
        self.assertEqual(rejected["outcome"], "HOLD")
        self.assertEqual(execute(REGISTRY, CAT, healthy, {}, live, desk, pages, state, SHA, now=later)["outcome"], "HOLD")
        def probe():
            return {"pages-probe.yml": {"id": 78, "run_attempt": 2, "head_sha": SHA, "conclusion": "success",
                    "created_at": later.isoformat(), "updated_at": later.isoformat(), "receipt_sha256": "0" * 64}}
        candidate = execute(REGISTRY, CAT, healthy, {}, live, desk, pages, state, SHA, now=later, receipt_reader=probe)
        self.assertEqual(candidate["outcome"], "CURRENT_PUBLICATION_EVIDENCE_FOR_EIC_REVIEW")
        self.assertEqual(candidate["ctoIndependentVerification"], "REQUIRED")
        reviewed = record_eic_review(candidate, healthy, later, candidate["executionId"])
        self.assertEqual(reviewed["reviewState"], "CTO_INDEPENDENT_REVIEW_REQUIRED")
        self.assertEqual(reviewed["eicVerification"]["evidenceSha256"], candidate["publicationEvidenceSha256"])
        self.assertEqual(record_eic_review(candidate, healthy, later, "wrong-run"), candidate)
        later_state = json.loads(json.dumps({"publisherRecoveryRobot": reviewed}))
        self.assertEqual(execute(REGISTRY, CAT, healthy, {}, live, desk, pages, later_state, SHA, now=later), reviewed)
        for bad in (dict(pages, checkedAt=self.now.isoformat()), dict(pages, publicationCurrentness={"current": False})):
            self.assertEqual(execute(REGISTRY, CAT, healthy, {}, live, desk, bad, state, SHA, now=later)["outcome"], "HOLD")

    def test_inline_cli_reused_for_second_incident(self):
        root = CATALOGUE.parents[1]
        env = dict(os.environ, GITHUB_ACTIONS="true", GITHUB_REPOSITORY=REPOSITORY, GITHUB_REF="refs/heads/main",
                   GITHUB_WORKFLOW_REF=f"{REPOSITORY}/.github/workflows/{DISPATCHER}@refs/heads/main",
                   GITHUB_RUN_ID="1234", EIC_SOURCE_COMMIT=SHA,
                   EIC_RECOVERY_OPERATION="public-probe:publisherRecovery:READ_ONLY")
        now = datetime.now(timezone.utc)
        cmd = [sys.executable, "-B", "scripts/publisher_recovery_robot.py", "--registry", str(CATALOGUE.with_name("newsroom-robots.json"))]
        with TemporaryDirectory() as temp:
            out = Path(temp)
            def test_cli(target, previous=None, cycle_at=None):
                cycle_at = cycle_at or now
                # Invalid publication plus explicit failed editorial gate. No network.
                data = {"cycle": cycle(cycle_at, issue=False), "draft": {"status": "VERIFIED_DRAFT",
                        "draftId": target, "createdAt": now.isoformat(), "targetPublication": "invalid"},
                        "live": {}, "desk": {}, "pages": {}, "previous": previous or {}}
                paths = []
                for k, v in data.items():
                    file = out / (k + ".json")
                    file.write_text(json.dumps(v), encoding="utf-8")
                    paths.extend(["--" + k, str(file)])
                result = out / "result.json"
                subprocess.run([*cmd, *paths, "--output", str(result)], cwd=root, env=env,
                               capture_output=True, check=True, timeout=6)
                return read(result)
            first = test_cli("incident-1")
            first_history = json.loads(json.dumps({"publisherRecoveryRobot": first, "publisherRecoveryAudit": [first]}))
            self.assertEqual(first, test_cli("incident-1", first_history))
            # This is a new case after EIC review, using the same installed registration.
            reviewed = dict(first, outcome="CURRENT_PUBLICATION_EVIDENCE_FOR_EIC_REVIEW",
                            reviewState="CTO_INDEPENDENT_REVIEW_REQUIRED")
            from scheduled_service_observation_v13 import unavailable, PUBLISHER
            task_observation = unavailable(PUBLISHER, now.isoformat())
            task_observation.update(provenance="OWNER_SUPPLIED_REPORT", enabled=True,
                last_run=dict(task_id=PUBLISHER, completed_at=now.isoformat(), result="SAFETY_BLOCKED"))
            second = test_cli("incident-2", {"publisherRecoveryRobot": reviewed,
                "scheduledPublisherObservation": task_observation}, datetime.now(timezone.utc))
            self.assertIn("SAFETY_BLOCK_REPORTED_NO_ALTERNATE_RETRY", second["reasonCodes"])
            self.assertFalse(second["scheduledPublisher"]["automatic_retry_allowed"])
            self.assertNotEqual(first["incidentId"], second["incidentId"])
            self.assertNotEqual(first["idempotencyKey"], second["idempotencyKey"])
            self.assertEqual(first["performed"], "RECHECK_RESERVED_DRAFT")
            self.assertEqual(second["outcome"], "HOLD")

    def test_unknown_fault_and_retry_budget(self):
        def unknown(now):
            data = cycle(now, issue=False)
            data.update(healthy=False, assignments=[{"robot": "unrecognized"}])
            return data
        stamps = [self.now + timedelta(minutes=m) for m in (0, 10, 16, 32)]
        first = execute(REGISTRY, CAT, unknown(stamps[0]), {}, {}, {}, {}, {}, SHA, now=stamps[0])
        self.assertIn("UNKNOWN_PUBLICATION_FAILURE", first["reasonCodes"])
        self.assertEqual(first["outcome"], "HOLD")
        self.assertEqual(first["publisherReceiptStatus"], "FALLBACK_RECEIPT_MISSING")
        prior = {"publisherRecoveryRobot": first}
        replay = execute(REGISTRY, CAT, unknown(stamps[1]), {}, {}, {}, {}, prior, SHA, now=stamps[1])
        self.assertEqual(first, replay)
        retry = execute(REGISTRY, CAT, unknown(stamps[2]), {}, {}, {}, {}, prior, SHA, now=stamps[2])
        self.assertEqual(retry["attempt"], 2)
        self.assertEqual(retry["incidentId"], first["incidentId"])
        limit = execute(REGISTRY, CAT, unknown(stamps[3]), {}, {}, {}, {},
                        {"publisherRecoveryRobot": retry, "publisherRecoveryAudit": [first, retry]},
                        SHA, now=stamps[3])
        self.assertEqual(limit, retry)

    def test_fallback_receipt_contradiction(self):
        data = cycle(self.now)
        data["execution"] = [{"robot": "live-publisher", "runId": 17, "headSha": SHA}]
        result = execute(REGISTRY, CAT, data, {}, {}, {}, {}, {}, SHA, now=self.now,
                         receipt_reader=lambda: {"live-publication-maintenance.yml": {
                             "id": 18, "head_sha": SHA, "receipt_sha256": "b"*64}})
        self.assertEqual(result["publisherReceiptStatus"], "FALLBACK_RECEIPT_CONTRADICTION")
        self.assertEqual(result["outcome"], "HOLD")

    def test_interrupted_cycle_preserves_audit_and_resumes_same_robot(self):
        from publisher_recovery_robot import merge_recovery_telemetry
        first = execute(REGISTRY, CAT, cycle(self.now), {}, {}, {}, {}, {}, SHA, now=self.now)
        previous = {"publisherRecoveryRobot": first, "publisherRecoveryAudit": [first]}
        interrupted = merge_recovery_telemetry(cycle(self.now), previous, {}, "failure")
        self.assertEqual(interrupted["publisherRecoveryRobot"]["outcome"], "HOLD")
        self.assertIn("RECOVERY_EXECUTION_INTERRUPTED_OR_MISSING", interrupted["publisherRecoveryRobot"]["reasonCodes"])
        self.assertEqual(interrupted["publisherRecoveryAudit"][0], first)
        restored = json.loads(json.dumps(interrupted))
        replay = execute(REGISTRY, CAT, cycle(self.now), {}, {}, {}, {}, restored, SHA, now=self.now)
        self.assertEqual(replay, first)
        self.assertEqual(len(merge_recovery_telemetry(cycle(self.now), restored, {}, "failure")["publisherRecoveryAudit"]), 2)

    def test_publisher_attempt_binding_and_incomplete_job_page(self):
        from publisher_recovery_robot import publisher_receipt, scan
        from unittest.mock import patch
        row = {"id": 5, "run_attempt": 2, "head_sha": SHA, "receipt_sha256": "f"*64}
        assigned = {"execution": [{"robot": "live-publisher", "runId": 5, "runAttempt": 1, "headSha": SHA}]}
        self.assertEqual(publisher_receipt({"live-publication-maintenance.yml": row}, assigned), "FALLBACK_RECEIPT_CONTRADICTION")
        assigned["execution"][0]["runAttempt"] = 2
        self.assertEqual(publisher_receipt({"live-publication-maintenance.yml": row}, assigned), "FALLBACK_RECEIPT_CORRELATED")
        def provider(url):
            if "/jobs?" in url:
                return {"total_count": 21, "jobs": []}
            return {"workflow_runs": [dict(row, head_branch="main")]}
        with patch("publisher_recovery_robot.get_json", side_effect=provider):
            receipts = scan()
        self.assertTrue(all(r["status"] == "RECEIPT_NOT_VERIFIED" for r in receipts.values()))

    def test_scan_retrieves_exact_assigned_publisher_attempt(self):
        from publisher_recovery_robot import scan
        from unittest.mock import patch
        calls = []
        def provider(url):
            calls.append(url)
            if url == "/actions/runs/81/attempts/2":
                return dict(id=81, run_attempt=2, head_branch="main", head_sha=SHA,
                            path=".github/workflows/live-publication-maintenance.yml", conclusion="failure")
            if url == "/actions/runs/81/attempts/2/jobs?per_page=20":
                return {"total_count": 1, "jobs": [dict(id=99,run_id=81,run_attempt=2,head_sha=SHA,steps=[])]}
            return {"workflow_runs": []}
        with patch("publisher_recovery_robot.get_json", side_effect=provider):
            result = scan(expected_publisher=(81,2))
        self.assertEqual(result["live-publication-maintenance.yml"]["id"], 81)
        self.assertIn("/actions/runs/81/attempts/2", calls)
        self.assertFalse(any("workflows/live-publication-maintenance.yml/runs" in x for x in calls))

    def test_scheduled_safety_block_and_missing_history_are_not_retried(self):
        from scheduled_service_observation_v13 import unavailable, PUBLISHER
        data=unavailable(PUBLISHER,self.now.isoformat())
        data.update(enabled=True,provenance="OWNER_SUPPLIED_REPORT",
                    last_run=dict(task_id=PUBLISHER,completed_at=self.now.isoformat(),result="SAFETY_BLOCKED"))
        first=execute(REGISTRY,CAT,cycle(self.now,issue=False),{},{},{},{},{},SHA,
                      now=self.now,scheduled=data)
        self.assertEqual(first["performed"],"RECONCILE_SCHEDULED_OUTCOME")
        self.assertEqual(first["outcome"],"HOLD")
        self.assertFalse(first["scheduledPublisher"]["automatic_retry_allowed"])
        self.assertIn("SAFETY_BLOCK_REPORTED_NO_ALTERNATE_RETRY",first["reasonCodes"])
        restored=json.loads(json.dumps({"publisherRecoveryRobot":first,"publisherRecoveryAudit":[first]}))
        self.assertEqual(execute(REGISTRY,CAT,cycle(self.now,issue=False),{},{},{},{},restored,SHA,
                                 now=self.now,scheduled=data),first)
        missing=execute(REGISTRY,CAT,cycle(self.now,issue=False),{},{},{},{},{},SHA,
                         now=self.now,scheduled=unavailable(PUBLISHER,self.now.isoformat()))
        self.assertIn("SCHEDULED_TASK_RUN_HISTORY_UNAVAILABLE",missing["reasonCodes"])
        self.assertEqual(missing["reviewState"],"HOLD")
