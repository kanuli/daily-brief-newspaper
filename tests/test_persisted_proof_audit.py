"""Synthetic original output and GitHub evidence; no news/model/network calls."""
import copy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import editorial_revision_trial as trial
import general_news_verified_producer as producer
import promote_verified_live_draft as publisher
import audit_persisted_editorial_proof as audit
import test_editorial_revision_trial as fixtures

NOW = datetime(2026, 10, 10, 4, 20, tzinfo=timezone.utc)
OWNER = {"workflow": "Editor-in-Chief Newsroom Assignment", "runId": "999"}
RAW = b"# SYNTHETIC original validator identity; no runnable source\n"
RAW_SHA = hashlib.sha1(b"blob " + str(len(RAW)).encode() + b"\0" + RAW).hexdigest()


class Store:
    def __init__(self, original):
        self.creates = []; self.writes = []; self.requests = []
        self.conflict = False; self.race = None
        claim = {"contract": original.CONTRACT, "contractRevision": audit.REVISION,
            "reviewedSources": original.REVIEWED_SOURCES, "claimedAt": "2026-10-10T03:47:26.078608Z",
            "expiresAt": "2026-10-10T04:07:26.078608Z", "dispatcherRunId": "900",
            "remainingAttempts": 0, "publicationPermissionGranted": False, "priorDraftId": "old-synthetic",
            "priorCapacity": copy.deepcopy(fixtures.BASE)}
        binding = {"childRunId": audit.CHILD, "dispatcherRunId": "900", "boundAt": "2026-10-10T03:47:54.211189Z",
                   "reviewedSources": original.REVIEWED_SOURCES}
        failure = {"status": "EDITORIAL_TRIAL_FAILED", "failureCode": "claim-child-code-binding-failed",
            "editorialOutcomeVerified": False, "publicationPermissionGranted": False,
            "remainingAttempts": 0, "childRunId": audit.CHILD}
        payload = fixtures.new_draft()
        candidate = {"id": "synthetic-proof-candidate", "title": "合成測試城市公布校園設施檢查安排",
            "source": "Synthetic Fixture", "url": "https://example.invalid/synthetic",
            "publishedAt": "2026-10-10T03:45:00Z", "provider": "fixture", "query": "fixture",
            "sourceEvidence": [{"name": "Synthetic Fixture", "url": "https://example.invalid/synthetic",
                                "facts": ["合成事實甲", "合成事實乙"]}],
            "verifiedCopy": {key: payload["articles"][0][key] for key in producer.COPY_FIELDS}}
        created = datetime(2026, 10, 10, 3, 53, 41, tzinfo=timezone.utc)
        payload.update(createdAt=trial.iso(created), targetPublication="2026-10-10T11:44:00+08:00",
                       articles=[producer.build_article(candidate, "world", created)])
        draft = copy.deepcopy(payload)
        draft["eicEditorialTrial"] = {"contractRevision": audit.REVISION, "dispatcherRunId": "900",
            "childRunId": audit.CHILD, "claimPath": audit.ORIGINAL_ROOT + ".claim.json",
            "draftPayloadSHA256": original.digest(payload), "reviewedSources": original.REVIEWED_SOURCES,
            "producerEngine": trial.producer_engine("false", "false", "true")}
        self.rows = {
            audit.ORIGINAL_ROOT + ".claim.json": {"sha": audit.CLAIM_SHA, "value": claim},
            audit.ORIGINAL_ROOT + ".run.json": {"sha": audit.BIND_SHA, "value": binding},
            audit.ORIGINAL_ROOT + ".result.json": {"sha": audit.RESULT_SHA, "value": failure},
            trial.DRAFT_PATH: {"sha": audit.DRAFT_SHA, "value": draft},
            trial.CAPACITY_PATH: {"sha": audit.CAPACITY_SHA, "value": copy.deepcopy(fixtures.BASE)}}
        self.original_rows = copy.deepcopy(self.rows)
        self.run = {"id": int(audit.CHILD), "head_sha": audit.HEAD, "run_attempt": 1, "event": "workflow_dispatch",
            "head_branch": "main", "repository": {"full_name": trial.REPOSITORY},
            "name": "General News Verified Producer", "path": ".github/workflows/general-news-producer.yml",
            "status": "completed", "conclusion": "failure", "updated_at": "2026-10-10T03:53:48Z"}
        self.job = {"id": 114125192569, "run_id": int(audit.CHILD), "name": "produce", "status": "completed",
            "conclusion": "failure", "steps": [
                {"name": "Produce outcome using Editor-in-Chief freshness targets", "conclusion": "success"},
                {"name": "Persist the verified draft on the isolated prepublish branch", "conclusion": "success"},
                {"name": audit.FINALIZER, "conclusion": "failure"}]}
        self.worker = {"id": 114124281051, "name": "workers (0)", "conclusion": "success"}
        self.publish = {"id": int(audit.PUBLISH_RUN), "status": "completed", "conclusion": "success",
                        "head_sha": audit.PUBLISH_HEAD, "head_branch": "main", "event": "workflow_dispatch",
                        "path": ".github/workflows/live-publication-maintenance.yml", "run_attempt": 1,
                        "name": "Live Publication Auto Maintenance", "repository": {"full_name": trial.REPOSITORY}}
        target = publisher.parse_iso(payload["targetPublication"])
        live = publisher.build_live(payload, {"items": [], "coverage": {}}, {}, target, payload["articles"])
        self.live = {"sha": audit.PUBLISHED_LIVE_SHA, "value": live}

    def read(self, path):
        return copy.deepcopy(self.rows.get(path))

    def headers(self):
        return {"User-Agent": "synthetic-no-network"}

    def json_request(self, request):
        self.requests.append(request.full_url)
        if request.full_url.endswith(audit.CHILD + "/jobs?per_page=100"):
            return {"jobs": copy.deepcopy([self.job, self.worker])}
        if request.full_url.endswith(audit.CHILD):
            return copy.deepcopy(self.run)
        if request.full_url.endswith(audit.PUBLISH_RUN):
            return copy.deepcopy(self.publish)
        raise AssertionError("unapproved endpoint")

    def published_live(self):
        return copy.deepcopy(self.live)

    def create(self, path, value):
        if path in self.rows:
            raise RuntimeError("create-only conflict")
        self.creates.append(path)
        self.rows[path] = {"sha": "synthetic-audit", "value": copy.deepcopy(value)}
        if self.race and path.endswith(".result.json"):
            self.rows[self.race]["sha"] = "raced"

    def compare_and_swap_capacity(self, sha, value):
        if self.conflict or self.rows[trial.CAPACITY_PATH]["sha"] != sha:
            return False
        self.writes.append(copy.deepcopy(value))
        self.rows[trial.CAPACITY_PATH] = {"sha": "synthetic-new-capacity", "value": value}
        return True


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); (self.root / "scripts").mkdir()
        (self.root / "scripts/editorial_revision_trial.py").write_bytes(RAW)
        self.calls = []
        def canonical(article, claim, now):
            self.calls.append(now)
            return trial.canonical_article_ok(article, claim, now)
        self.original = types.SimpleNamespace(CONTRACT=trial.CONTRACT, CONTRACT_REVISION=trial.CONTRACT_REVISION,
            REVIEWED_SOURCES=copy.deepcopy(trial.REVIEWED_SOURCES), reviewed_code=lambda root: True,
            checked_engine=trial.checked_engine, producer_engine=trial.producer_engine, digest=trial.digest,
            canonical_article_ok=canonical)
        self.store = Store(self.original)
        self.pin = patch.object(audit, "ORIGINAL_MODULE_BLOB", RAW_SHA); self.pin.start(); self.addCleanup(self.pin.stop)

    def run_audit(self, now=NOW, owner=OWNER, clock=None):
        return audit.audit(self.root, self.original, self.store, owner, now, clock=clock or (lambda: now))

    def assert_preserved(self):
        for kind in ("claim", "run", "result"):
            path = audit.ORIGINAL_ROOT + "." + kind + ".json"
            self.assertEqual(self.store.rows[path], self.store.original_rows[path])
        self.assertEqual(self.store.rows[trial.DRAFT_PATH], self.store.original_rows[trial.DRAFT_PATH])

    def test_exact_success_after_original_expiry_uses_REAL_now_and_one_CAS(self):
        result = self.run_audit()
        self.assertTrue(result["audited"], result)
        self.assertEqual(self.calls, [NOW])
        self.assertEqual(len(self.store.creates), 2); self.assertEqual(len(self.store.writes), 1)
        self.assertEqual(self.store.writes[0]["status"], "DEGRADED_LOCAL_FALLBACK")
        self.assertFalse(self.store.writes[0]["publicationPermissionGranted"])
        record = self.store.read(audit.AUDIT_ROOT + ".result.json")["value"]
        self.assertEqual(record["sourceCalls"], 0); self.assertEqual(record["modelCalls"], 0)
        self.assertFalse(record["originalTrialExpiryExtended"])
        self.assert_preserved()
        self.assertFalse(self.run_audit()["audited"]); self.assertEqual(len(self.store.writes), 1)

    def test_wrong_owner_or_approval_window_never_consumes_permission(self):
        with self.assertRaises(trial.ProbeFailure):
            self.run_audit(owner={"workflow": "Leaf robot", "runId": "999"})
        for minute in (10, 45):
            self.assertFalse(self.run_audit(datetime(2026, 10, 10, 4, minute, tzinfo=timezone.utc))["audited"])
        self.assertEqual(self.store.creates + self.store.writes + self.store.requests, [])

    def test_original_module_mismatch_fails_without_capacity_write(self):
        (self.root / "scripts/editorial_revision_trial.py").write_bytes(b"changed")
        self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_reviewed_code_mismatch_fails(self):
        self.original.reviewed_code = lambda root: False
        self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_changed_immutable_evidence_is_not_accepted(self):
        for path in self.store.original_rows:
            with self.subTest(path=path):
                self.store = Store(self.original); self.store.rows[path]["sha"] = "changed"
                self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_child_replay_wrong_head_or_late_original_work_fails(self):
        for delta in ({"run_attempt": 2}, {"run_attempt": True}, {"head_sha": "other"},
                      {"conclusion": "success"}, {"updated_at": "2026-10-10T04:08:00Z"}):
            with self.subTest(delta=delta):
                self.store = Store(self.original); self.store.run.update(delta)
                self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_other_failed_step_or_missing_persist_evidence_fails(self):
        for missing in (False, True):
            self.store = Store(self.original)
            if missing: self.store.job["steps"].pop(1)
            else: self.store.job["steps"].append({"name": "Source verification", "conclusion": "failure"})
            self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_original_creation_after_expiry_is_never_rescued(self):
        self.store.rows[trial.DRAFT_PATH]["value"]["createdAt"] = "2026-10-10T04:08:00Z"
        self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_altered_payload_stamp_or_locator_fails(self):
        for field, value in (("body", "短"), ("sourceUrl", "https://newspicks.com/news/123")):
            self.store = Store(self.original); self.store.rows[trial.DRAFT_PATH]["value"]["articles"][0][field] = value
            self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_independent_canonical_gate_rejects_even_if_payload_rehashed(self):
        d = self.store.rows[trial.DRAFT_PATH]["value"]; d["articles"][0]["body"] = "短"
        p = copy.deepcopy(d); p.pop("eicEditorialTrial")
        d["eicEditorialTrial"]["draftPayloadSHA256"] = trial.digest(p)
        self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_wrong_actual_publication_payload_or_job_fails(self):
        for changed in ("payload", "job", "sha"):
            self.store = Store(self.original)
            if changed == "payload": self.store.live["value"]["items"][0]["body"] = "changed"
            elif changed == "job": self.store.publish["conclusion"] = "failure"
            else: self.store.live["sha"] = "other"
            self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_expiry_during_audit_never_CAS(self):
        late = datetime(2026, 10, 10, 4, 45, tzinfo=timezone.utc)
        self.assertFalse(self.run_audit(clock=lambda: late)["audited"]); self.assertEqual(self.store.writes, [])

    def test_concurrent_capacity_change_never_overwrites(self):
        self.store.conflict = True
        self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])
        self.assert_preserved()

    def test_draft_race_after_positive_proof_never_CAS(self):
        self.store.race = trial.DRAFT_PATH
        self.assertFalse(self.run_audit()["audited"]); self.assertEqual(self.store.writes, [])

    def test_store_allows_only_two_extra_create_only_audit_records(self):
        self.assertTrue(audit.AuditStore.allowed_path(audit.AUDIT_ROOT + ".claim.json"))
        self.assertTrue(audit.AuditStore.allowed_path(audit.AUDIT_ROOT + ".result.json"))
        for path in ("data/live.json", "data/latest.json", audit.AUDIT_ROOT + ".run.json", "data/random.json"):
            self.assertFalse(audit.AuditStore.allowed_path(path))

    def test_owner_hook_runs_before_classification_and_reloads_CAPACITY(self):
        workflow = (ROOT / ".github/workflows/editor-in-chief-newsroom-assignment.yml").read_text()
        self.assertLess(workflow.index("python scripts/audit_persisted_editorial_proof.py"), workflow.index("python scripts/editorial_revision_trial.py inspect"))
        self.assertIn('contents/data/producer-capacity.json?ref=prepublish-news', workflow)
        self.assertEqual(trial.CONTRACT_REVISION, audit.REVISION)


if __name__ == "__main__":
    unittest.main()
