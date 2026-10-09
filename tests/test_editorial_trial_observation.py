import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import editorial_trial_observation as observation

NOW = datetime(2026, 10, 9, 4, 35, tzinfo=timezone.utc)
REPOSITORY = "kanuli/daily-brief-newspaper"
REVISION = "a" * 64
CONTRACT = {"protocol": "synthetic-fixed-reviewed-contract", "gatesUnchanged": True}
SOURCES = {"scripts/synthetic.py": "b" * 64}
CAPACITY_SHA = "c" * 40
CAPACITY = {"status": "LOCAL_FALLBACK_FAILED", "workflowRunId": "800"}
CLAIM_PATH = f"{observation.TRIAL_ROOT}/{REVISION}.claim.json"
RUN_PATH = f"{observation.TRIAL_ROOT}/{REVISION}.run.json"
RESULT_PATH = f"{observation.TRIAL_ROOT}/{REVISION}.result.json"


def iso(moment):
    return moment.isoformat().replace("+00:00", "Z")


class Store:
    def __init__(self):
        claimed = NOW - timedelta(minutes=2)
        self.rows = {
            CLAIM_PATH: {"sha": "immutable-claim-sha", "value": {
                "schemaVersion": 1, "owner": "Site Editor-in-Chief",
                "scope": "single-reviewed-editorial-code-trial", "contractRevision": REVISION,
                "contract": copy.deepcopy(CONTRACT), "reviewedSources": copy.deepcopy(SOURCES),
                "priorCapacitySHA": CAPACITY_SHA, "priorCapacity": copy.deepcopy(CAPACITY),
                "dispatcherRunId": "900", "assignmentId": "synthetic-assignment",
                "attempt": 1, "maxAttempts": 1, "remainingAttempts": 0,
                "publicationPermissionGranted": False,
                "claimedAt": iso(claimed), "expiresAt": iso(claimed + timedelta(minutes=20)),
            }},
            RUN_PATH: {"sha": "immutable-binding-sha", "value": {
                "schemaVersion": 1, "contractRevision": REVISION,
                "reviewedSources": copy.deepcopy(SOURCES), "dispatcherRunId": "900",
                "childRunId": "901", "claimPath": CLAIM_PATH,
                "boundAt": iso(NOW - timedelta(minutes=1)),
            }},
        }
        self.run = {
            "id": 901, "repository": {"full_name": REPOSITORY},
            "name": observation.CHILD_WORKFLOW, "path": observation.CHILD_PATH,
            "event": "workflow_dispatch", "head_branch": "main", "run_attempt": 1,
            "status": "in_progress", "conclusion": None,
        }
        self.reads = []
        self.requests = []
        self.writes = []
        self.network_error = None
        self.result_during_request = False

    def read(self, path):
        self.reads.append(path)
        return copy.deepcopy(self.rows.get(path))

    def headers(self):
        return {"Authorization": "Bearer synthetic-test-only-token", "Accept": "application/vnd.github+json"}

    def json_request(self, request):
        self.requests.append(request)
        if self.network_error is not None:
            raise self.network_error
        if self.result_during_request:
            self.rows[RESULT_PATH] = {"sha": "immutable-result", "value": {"status": "EDITORIAL_TRIAL_FAILED"}}
        return copy.deepcopy(self.run)

    def create(self, *args):
        self.writes.append(args)
        raise AssertionError("observation must never write")

    compare_and_swap_capacity = create


def observe(store, **changes):
    arguments = dict(
        store=store, now=NOW, repository=REPOSITORY, contract_revision=REVISION,
        contract=CONTRACT, reviewed_sources=SOURCES, prior_capacity_sha=CAPACITY_SHA,
        prior_capacity=CAPACITY,
    )
    arguments.update(changes)
    return observation.observe_pending_trial(**arguments)


class ObservationTests(unittest.TestCase):
    def test_exact_matching_active_child_is_pending_read_only(self):
        store = Store()
        before = copy.deepcopy(store.rows)
        result = observe(store)
        self.assertIs(result["pending"], True)
        self.assertEqual(result["trialChildRunId"], "901")
        self.assertEqual(result["trialDispatcherRunId"], "900")
        self.assertEqual(result["trialExpiresAt"], before[CLAIM_PATH]["value"]["expiresAt"])
        self.assertEqual(store.rows, before)
        self.assertEqual(store.writes, [])
        self.assertEqual(len(store.requests), 1)
        self.assertEqual(store.requests[0].method, "GET")
        self.assertEqual(store.requests[0].full_url,
                         f"https://api.github.com/repos/{REPOSITORY}/actions/runs/901")
        self.assertNotIn("eligible", result)
        self.assertNotIn("publicationPermissionGranted", result)

    def test_only_explicit_active_statuses_accepted(self):
        for status in observation.ACTIVE_STATUSES:
            with self.subTest(status=status):
                store = Store(); store.run["status"] = status
                self.assertTrue(observe(store)["pending"])

    def test_missing_binding_claim_or_record_shape_never_looks_active(self):
        for path in (CLAIM_PATH, RUN_PATH):
            for malformed in (None, {}, {"sha": "", "value": {}}, {"sha": "x", "value": []}):
                with self.subTest(path=path, malformed=malformed):
                    store = Store()
                    if malformed is None:
                        store.rows.pop(path)
                    else:
                        store.rows[path] = malformed
                    self.assertFalse(observe(store)["pending"])
                    self.assertEqual(store.requests, [])

    def test_any_recorded_result_ends_pending_even_if_api_would_still_be_active(self):
        for value in ({"status": "EDITORIAL_TRIAL_FAILED"}, {"status": "VERIFIED_NEW_DRAFT"}, {}):
            with self.subTest(value=value):
                store = Store(); store.rows[RESULT_PATH] = {"sha": "immutable-result", "value": value}
                self.assertFalse(observe(store)["pending"])
                self.assertEqual(store.requests, [])

    def test_result_created_during_run_read_ends_pending(self):
        store = Store(); store.result_during_request = True
        self.assertFalse(observe(store)["pending"])
        self.assertEqual(store.writes, [])

    def test_invalid_claim_identity_budget_capacity_or_permission_is_held(self):
        changes = {
            "schemaVersion": True, "owner": "leaf robot", "scope": "arbitrary-scope",
            "contractRevision": "d" * 64, "contract": {"protocol": "other"},
            "reviewedSources": {}, "priorCapacitySHA": "newer-capacity",
            "priorCapacity": {"status": "AVAILABLE"}, "dispatcherRunId": "0",
            "assignmentId": "", "attempt": True, "maxAttempts": 2,
            "remainingAttempts": 1, "publicationPermissionGranted": True,
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                store = Store(); store.rows[CLAIM_PATH]["value"][field] = value
                self.assertFalse(observe(store)["pending"])
                self.assertEqual(store.requests, [])

    def test_invalid_binding_identity_or_replay_is_held(self):
        changes = {
            "schemaVersion": True, "contractRevision": "d" * 64,
            "reviewedSources": {}, "dispatcherRunId": "902",
            "claimPath": "another-claim", "childRunId": "901/../../other",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                store = Store(); store.rows[RUN_PATH]["value"][field] = value
                self.assertFalse(observe(store)["pending"])
                self.assertEqual(store.requests, [])

    def test_invalid_future_expired_or_extended_clocks_are_held(self):
        cases = (
            (CLAIM_PATH, "claimedAt", iso(NOW + timedelta(seconds=1))),
            (CLAIM_PATH, "expiresAt", iso(NOW - timedelta(seconds=1))),
            (CLAIM_PATH, "expiresAt", iso(NOW + timedelta(minutes=19))),
            (RUN_PATH, "boundAt", iso(NOW + timedelta(seconds=1))),
            (RUN_PATH, "boundAt", iso(NOW - timedelta(minutes=3))),
            (RUN_PATH, "boundAt", "2026-10-09T04:34:00"),
            (CLAIM_PATH, "claimedAt", "invalid"),
        )
        for path, field, value in cases:
            with self.subTest(path=path, field=field, value=value):
                store = Store(); store.rows[path]["value"][field] = value
                self.assertFalse(observe(store)["pending"])
                self.assertEqual(store.requests, [])
        self.assertFalse(observe(Store(), now=NOW + timedelta(minutes=19))["pending"])

    def test_wrong_run_identity_workflow_attempt_branch_or_completed_is_held(self):
        changes = {
            "id": 902, "repository": {"full_name": "other/repository"},
            "name": "Other Workflow", "path": ".github/workflows/other.yml",
            "event": "push", "head_branch": "other-branch", "run_attempt": 2,
            "status": "completed", "conclusion": "failure",
        }
        for field, value in changes.items():
            with self.subTest(field=field):
                store = Store(); store.run[field] = value
                self.assertFalse(observe(store)["pending"])
                self.assertEqual(store.writes, [])
        for field in ("id", "repository", "name", "path", "event", "head_branch", "run_attempt", "status", "conclusion"):
            with self.subTest(missing=field):
                store = Store(); store.run.pop(field)
                self.assertFalse(observe(store)["pending"])
        store = Store(); store.run["run_attempt"] = True
        self.assertFalse(observe(store)["pending"])

    def test_unknown_run_or_network_error_never_leaks_or_becomes_pending(self):
        for run in (None, {}, [], "invalid"):
            with self.subTest(run=run):
                store = Store(); store.run = run
                self.assertFalse(observe(store)["pending"])
        store = Store(); store.network_error = RuntimeError("synthetic-test-only-token secret API body")
        result = observe(store)
        self.assertFalse(result["pending"])
        self.assertNotIn("token", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))

    def test_invalid_expectations_cannot_extend_expiry_or_read_another_endpoint(self):
        cases = (
            {"expiry_minutes": 21}, {"expiry_minutes": True},
            {"repository": "owner/repo/actions/runs/other"},
            {"contract_revision": "../other"}, {"now": NOW.replace(tzinfo=None)},
            {"prior_capacity": None}, {"prior_capacity": {"status": "AVAILABLE"}},
            {"prior_capacity": {"status": "LOCAL_FALLBACK_FAILED", "capabilityOnly": True}},
        )
        for change in cases:
            with self.subTest(change=change):
                store = Store()
                self.assertFalse(observe(store, **change)["pending"])
                self.assertEqual(store.reads, [])
                self.assertEqual(store.requests, [])


if __name__ == "__main__":
    unittest.main()
