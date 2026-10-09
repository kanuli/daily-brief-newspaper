import copy
import contextlib
from datetime import datetime, timedelta, timezone
import importlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import editorial_revision_trial as trial
import general_news_verified_producer as producer
import probe_general_news_fallback_capability as capability
import newsroom_control_plane as control

NOW = datetime(2026, 10, 9, 16, 20, tzinfo=timezone.utc)
EIC = {"runId": "900", "workflow": "Editor-in-Chief Newsroom Assignment"}
CHILD = {"runId": "901", "workflow": "General News Verified Producer"}
LOCAL_ENGINE = trial.producer_engine("false", "false", "true")
COPILOT_ENGINE = trial.producer_engine("true", "true", "false")
BASE = {
    "status": "LOCAL_FALLBACK_FAILED", "workflowRunId": trial.FAILED_RUN,
    "checkedAt": trial.FAILED_CHECKED_AT, "localFallbackModel": trial.FAILED_MODEL,
    "reason": "Synthetic fixture representing actual editorial rejection, not news",
}


class Store:
    def __init__(self):
        self.rows = {
            trial.CAPACITY_PATH: {"sha": trial.FAILED_CAPACITY_SHA, "value": copy.deepcopy(BASE)},
            trial.DRAFT_PATH: {"sha": "old-draft-sha", "value": {"draftId": "old-draft"}},
            f"{trial.TRIAL_ROOT}/{trial.PREDECESSOR_CONTRACT}.result.json": {
                "sha": trial.PREDECESSOR_RESULT_SHA,
                "value": {"status": "EDITORIAL_TRIAL_FAILED", "childRunId": trial.PREDECESSOR_CHILD,
                          "editorialOutcomeVerified": False, "failureCode": "missing-engine-evidence"},
            },
        }
        self.capacity_writes = []
        self.creates = []
        self.failed_run = {
            "id": int(trial.FAILED_RUN), "repository": {"full_name": trial.REPOSITORY},
            "name": "General News Verified Producer", "path": ".github/workflows/general-news-producer.yml",
            "event": "workflow_dispatch", "head_branch": "main", "head_sha": trial.FAILED_HEAD,
            "run_attempt": 1, "status": "completed", "conclusion": "failure",
        }
        self.failed_job = {
            "id": trial.FAILED_JOB, "run_id": int(trial.FAILED_RUN), "name": "produce",
            "status": "completed", "conclusion": "failure",
            "steps": [{"name": "Fail non-capacity verification/copy errors", "conclusion": "failure"}],
        }
        self.cancelled_run = {**self.failed_run, "id": int(trial.PREDECESSOR_CHILD),
                              "head_sha": trial.PREDECESSOR_HEAD, "conclusion": "cancelled"}
        self.cancelled_job = {**self.failed_job, "id": trial.PREDECESSOR_JOB,
                              "run_id": int(trial.PREDECESSOR_CHILD), "conclusion": "cancelled",
                              "steps": [{"name": "Run open-source local capacity fallback", "conclusion": "cancelled"}]}

    def ledger_ready(self):
        return True

    def headers(self):
        return {"User-Agent": "synthetic-observer-test"}

    def json_request(self, request):
        cancelled_url = f"/actions/runs/{trial.PREDECESSOR_CHILD}"
        if request.full_url.endswith(cancelled_url):
            return copy.deepcopy(self.cancelled_run)
        if request.full_url.endswith(cancelled_url + "/jobs?per_page=100"):
            return {"jobs": [copy.deepcopy(self.cancelled_job)]}
        failed_url = f"/actions/runs/{trial.FAILED_RUN}"
        if request.full_url.endswith(failed_url):
            return copy.deepcopy(self.failed_run)
        if request.full_url.endswith(failed_url + "/jobs?per_page=100"):
            return {"jobs": [copy.deepcopy(self.failed_job)]}
        return {
            "id": 901, "repository": {"full_name": trial.REPOSITORY},
            "name": CHILD["workflow"], "path": ".github/workflows/general-news-producer.yml",
            "event": "workflow_dispatch", "head_branch": "main", "run_attempt": 1,
            "status": "in_progress", "conclusion": None,
        }

    def read(self, path):
        return copy.deepcopy(self.rows.get(path))

    def create(self, path, value):
        if path in self.rows:
            raise trial.ProbeFailure("store", "duplicate-immutable-record")
        self.creates.append(path)
        self.rows[path] = {"sha": "immutable", "value": copy.deepcopy(value)}

    def compare_and_swap_capacity(self, sha, value):
        if self.rows[trial.CAPACITY_PATH]["sha"] != sha:
            return False
        self.capacity_writes.append(copy.deepcopy(value))
        self.rows[trial.CAPACITY_PATH] = {"sha": "new-capacity", "value": copy.deepcopy(value)}
        return True


def assignment(permit):
    return {"robot": "general-producer", "workflow": "general-news-producer.yml",
            "assignmentId": "eic-assignment", "status": "reviewed-editorial-trial",
            "dispatchable": True, "dispatchInputs": {
                "editorial_trial_contract": trial.CONTRACT_REVISION,
                "editorial_trial_dispatcher_run": permit["dispatcherRunId"],
            }}


def claimed(store):
    permit = trial.eligible(ROOT, store, EIC, NOW)
    trial.claim(ROOT, store, permit, assignment(permit), EIC, NOW)
    return trial.bind(ROOT, store, trial.CONTRACT_REVISION, EIC["runId"], CHILD, NOW)


def new_draft():
    # Deliberately synthetic test-only prose and reserved .invalid URL. No model,
    # news search, article source fetch, publication or real news payload here.
    body = "合成測試文字用於驗證程式規則並非真實新聞內容。" * 5
    candidate = {
        "id": "synthetic-candidate", "title": "合成測試城市公布校園設施檢查安排",
        "source": "Synthetic Fixture", "url": "https://example.invalid/synthetic",
        "publishedAt": trial.iso(NOW), "provider": "fixture", "query": "fixture",
        "sourceEvidence": [{"name": "Synthetic Fixture", "url": "https://example.invalid/synthetic",
                            "facts": ["合成事實甲", "合成事實乙"]}],
        "verifiedCopy": {field: "合成測試文字" for field in producer.COPY_FIELDS},
    }
    candidate["verifiedCopy"].update(title=candidate["title"], body=body + "\n\n" + body)
    article = producer.build_article(candidate, "world", NOW)
    return {"status": "VERIFIED_DRAFT", "publicationType": "LIVE", "draftId": "new-synthetic-draft",
            "createdAt": trial.iso(NOW), "articles": [article]}


def classified_trial(permit):
    """Exercise the actual classifier with synthetic non-publication state."""
    previous = {
        "cycleId": "prior-normal-path", "checkedAt": trial.iso(NOW - timedelta(hours=1)),
        "assignments": [{"robot": "general-producer", "workflow": "general-news-producer.yml",
                         "attempt": 2, "mode": "normal", "maxRuntimeMinutes": 15,
                         "outcomeBefore": {"prepublishDraftId": None}}],
        "execution": [{"workflow": "general-news-producer.yml", "dispatched": True}],
    }
    fixtures = {
        "staging": {"lastSearchAt": trial.iso(NOW), "desks": {"world": [{"publishedAt": trial.iso(NOW)}]}},
        "prepublish": {}, "producer-capacity": BASE,
        "freshness": {"desks": {"world": {"fresh": False, "dailySynced": True, "newestAgeHours": 10}}},
        "editor-status": {"findings": [], "voiceWorkflowAudit": {"coverageComplete": True}},
        "sentinel": {}, "pages-status": {"checkedAt": trial.iso(NOW), "match": True},
        "pages-deployment": [], "editorial-trial": permit, "previous-assignments": previous,
        "latest": {"date": NOW.astimezone(producer.HKT).date().isoformat()},
        "live": {"lastUpdated": trial.iso(NOW - timedelta(hours=10))}, "desk": {},
        "stocks": {"lastCheckedAt": trial.iso(NOW)}, "tts": {},
    }
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        argv = ["classifier", "--registry", str(ROOT / "config/newsroom-robots.json")]
        for name, value in fixtures.items():
            path = root / (name + ".json")
            path.write_text(json.dumps(value), encoding="utf-8")
            argv.extend(["--" + name, str(path)])
        output = root / "assignment.json"
        argv.extend(["--stock-rc", "0", "--publication-rc", "0", "--vocab-rc", "0",
                     "--trigger-workflow", "General News Verified Producer", "--trigger-conclusion", "failure",
                     "--now", trial.iso(NOW), "--output", str(output)])
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            control.main()
        return json.loads(output.read_text(encoding="utf-8"))


class TrialTests(unittest.TestCase):
    def test_reviewed_sources_exact(self):
        self.assertTrue(trial.reviewed_code(ROOT))

    def test_current_revision_requires_the_exact_cancelled_predecessor_record(self):
        path = f"{trial.TRIAL_ROOT}/{trial.PREDECESSOR_CONTRACT}.result.json"
        for change in ("missing", "sha", "success", "other-child", "failure-code"):
            store = Store()
            if change == "missing":
                store.rows.pop(path)
            elif change == "sha":
                store.rows[path]["sha"] = "different-proof"
            elif change == "success":
                store.rows[path]["value"].update(status="VERIFIED_NEW_DRAFT", editorialOutcomeVerified=True)
            elif change == "other-child":
                store.rows[path]["value"]["childRunId"] = "another-child"
            else:
                store.rows[path]["value"]["failureCode"] = "other-failure"
            with self.subTest(change=change):
                self.assertEqual(trial.eligible(ROOT, store, EIC, NOW)["reason"],
                                 "reviewed-cancelled-predecessor-record-not-proven")

    def test_exact_failed_run_and_job_are_required_without_writes(self):
        for delta in ({"id": 1}, {"repository": {"full_name": "other/repo"}},
                      {"head_sha": "other"}, {"head_branch": "other"},
                      {"run_attempt": True}, {"run_attempt": 2},
                      {"status": "in_progress"}, {"conclusion": "success"}):
            store = Store(); store.failed_run.update(delta)
            with self.subTest(run=delta):
                self.assertEqual(trial.eligible(ROOT, store, EIC, NOW)["reason"],
                                 "exact-prior-editorial-production-failure-not-proven")
                self.assertEqual(store.creates + store.capacity_writes, [])
        for delta in ({"id": 1}, {"run_id": 1}, {"name": "other"},
                      {"status": "in_progress"}, {"conclusion": "success"}, {"steps": []}):
            store = Store(); store.failed_job.update(delta)
            with self.subTest(job=delta):
                self.assertFalse(trial.eligible(ROOT, store, EIC, NOW)["eligible"])
                self.assertEqual(store.creates + store.capacity_writes, [])

    def test_failed_run_transport_error_is_closed_not_content_repair(self):
        store = Store()
        with patch.object(store, "json_request", side_effect=TimeoutError("synthetic")):
            self.assertFalse(trial.eligible(ROOT, store, EIC, NOW)["eligible"])
        self.assertEqual(store.creates + store.capacity_writes, [])

    def test_new_model_is_not_the_failed_small_model_and_claim_is_bound(self):
        self.assertEqual(trial.MODEL, "gemma3:4b-it-qat")
        self.assertNotEqual(trial.MODEL, trial.FAILED_MODEL)
        store = Store(); state = claimed(store)
        self.assertEqual(state["claim"]["failedProduction"], trial.CONTRACT["priorFailedProduction"])
        store.rows[trial.record_path("claim")]["value"]["failedProduction"]["run"] = "another"
        with self.assertRaises(trial.ProbeFailure):
            trial.bind(ROOT, store, trial.CONTRACT_REVISION, EIC["runId"], CHILD, NOW)

    def test_exact_owner_disallowed_cancellation_is_required_before_new_model_admission(self):
        for delta in ({"id": 1}, {"head_sha": "other"}, {"head_branch": "other"},
                      {"run_attempt": True}, {"run_attempt": 2}, {"status": "in_progress"},
                      {"conclusion": "success"}, {"conclusion": "failure"}):
            store = Store(); store.cancelled_run.update(delta)
            with self.subTest(run=delta):
                self.assertEqual(trial.eligible(ROOT, store, EIC, NOW)["reason"],
                                 "exact-owner-disallowed-trial-cancellation-not-proven")
                self.assertEqual(store.creates + store.capacity_writes, [])
        for delta in ({"id": 1}, {"run_id": 1}, {"conclusion": "success"}, {"steps": []}):
            store = Store(); store.cancelled_job.update(delta)
            with self.subTest(job=delta):
                self.assertFalse(trial.eligible(ROOT, store, EIC, NOW)["eligible"])
                self.assertEqual(store.creates + store.capacity_writes, [])

    def test_meaningful_current_revision_preserves_spent_predecessor_records(self):
        store = Store()
        old_claim = f"{trial.TRIAL_ROOT}/{trial.PREDECESSOR_CONTRACT}.claim.json"
        store.rows[old_claim] = {"sha": "immutable-old-claim", "value": {"remainingAttempts": 0}}
        before = copy.deepcopy(store.rows)
        self.assertTrue(trial.eligible(ROOT, store, EIC, NOW)["eligible"])
        state = claimed(store)
        self.assertNotEqual(trial.CONTRACT_REVISION, trial.PREDECESSOR_CONTRACT)
        for path in (old_claim, f"{trial.TRIAL_ROOT}/{trial.PREDECESSOR_CONTRACT}.result.json"):
            self.assertEqual(store.rows[path], before[path])
        self.assertEqual(state["claim"]["predecessorResultSHA"], trial.PREDECESSOR_RESULT_SHA)
        self.assertEqual(trial.CONTRACT["copyFields"], list(producer.COPY_FIELDS))

    def test_runtime_capacity_not_reset_by_claim_or_bind(self):
        store = Store()
        claimed(store)
        self.assertEqual(store.read(trial.CAPACITY_PATH)["value"], BASE)
        self.assertEqual(store.capacity_writes, [])

    def test_failed_result_preserves_old_failure(self):
        store = Store(); state = claimed(store)
        self.assertFalse(trial.finish(ROOT, store, state, None, CHILD, NOW, engine=LOCAL_ENGINE))
        self.assertEqual(store.read(trial.CAPACITY_PATH)["value"], BASE)
        self.assertEqual(store.read(trial.record_path("result"))["value"]["status"], "EDITORIAL_TRIAL_FAILED")
        self.assertFalse(trial.eligible(ROOT, store, EIC, NOW)["eligible"])

    def test_duplicate_claim_and_different_head_cannot_renew(self):
        store = Store(); claimed(store)
        with patch.dict(os.environ, {"GITHUB_SHA": "new-unrelated-head"}):
            self.assertEqual(trial.eligible(ROOT, store, EIC, NOW)["reason"], "semantic-trial-budget-consumed")

    def test_cosmetic_source_hash_change_cannot_mint_semantic_budget(self):
        before = trial.CONTRACT_REVISION
        with patch.dict(trial.REVIEWED_SOURCES, {"scripts/general_news_local_fallback.py": "0" * 64}):
            self.assertFalse(trial.eligible(ROOT, Store(), EIC, NOW)["eligible"])
            self.assertEqual(trial.CONTRACT_REVISION, before)

    def test_cosmetic_change_even_reviewed_still_uses_same_consumed_contract(self):
        store = Store(); claimed(store)
        with patch.object(trial, "reviewed_code", return_value=True):
            self.assertEqual(trial.eligible(ROOT, store, EIC, NOW)["reason"], "semantic-trial-budget-consumed")

    def test_child_replay_and_parallel_second_child_are_fatal(self):
        store = Store(); claimed(store)
        with self.assertRaises(trial.ProbeFailure):
            trial.bind(ROOT, store, trial.CONTRACT_REVISION, EIC["runId"], {"runId": "902"}, NOW)

    def test_self_asserted_input_without_claim_is_fatal(self):
        with self.assertRaises(trial.ProbeFailure):
            trial.bind(ROOT, Store(), trial.CONTRACT_REVISION, EIC["runId"], CHILD, NOW)

    def test_manual_normal_run_cannot_bypass_failed_capacity(self):
        with self.assertRaises(trial.ProbeFailure):
            trial.bind(ROOT, Store(), "", "", CHILD, NOW)

    def test_rerun_owner_context_rejected(self):
        env = {"GITHUB_REPOSITORY": trial.REPOSITORY, "GITHUB_WORKFLOW": CHILD["workflow"],
               "GITHUB_RUN_ID": CHILD["runId"], "GITHUB_RUN_ATTEMPT": "2"}
        with patch.dict(os.environ, env), self.assertRaises(trial.ProbeFailure):
            trial.context("child")

    def test_future_permit_and_claim_rejected(self):
        store = Store(); permit = trial.eligible(ROOT, store, EIC, NOW)
        permit["checkedAt"] = trial.iso(NOW + timedelta(seconds=1))
        with self.assertRaises(trial.ProbeFailure):
            trial.claim(ROOT, store, permit, assignment(permit), EIC, NOW)
        self.assertNotIn(trial.record_path("claim"), store.rows)

    def test_binding_clock_cannot_predate_claim(self):
        store = Store(); state = claimed(store)
        state["run"]["boundAt"] = trial.iso(NOW - timedelta(seconds=1))
        store.rows[trial.record_path("run")]["value"] = copy.deepcopy(state["run"])
        self.assertFalse(trial.finish(ROOT, store, state, None, CHILD, NOW, engine=LOCAL_ENGINE))
        self.assertEqual(store.capacity_writes, [])

    def test_runtime_probe_cannot_reclaim_actual_editorial_rejection(self):
        store = Store()
        with patch.object(capability, "revision", return_value=capability.REVIEWED_REVISION):
            result = capability.prepare(ROOT, store, ROOT / "unused-state.json")
        self.assertFalse(result["claimed"])
        self.assertEqual(result["reason"], "actual-producer-failure-requires-editorial-review")
        self.assertEqual(store.creates, [])
        self.assertEqual(capability.REVIEWED_REVISION,
                         "eb3707b28647cbb1a78a306446df9f4c7422f951dd1b63fbd851e5d9289c9a1e")

    def test_runtime_available_result_never_erases_actual_editorial_failure(self):
        store = Store()
        moment = capability.stamp()
        state = {"probeRevision": capability.REVIEWED_REVISION, "claimedAt": moment,
                 "priorCapacity": copy.deepcopy(BASE), "priorCapacitySHA": trial.FAILED_CAPACITY_SHA}
        store.create(capability.claim_path(capability.REVIEWED_REVISION), state)
        result = {
            "schemaVersion": 1, "owner": "Site Editor-in-Chief", "scope": capability.PROBE_SCOPE,
            "probeRevision": capability.REVIEWED_REVISION, "checkedAt": capability.stamp(),
            "attempt": 1, "remainingAttempts": 0, "status": "LOCAL_FALLBACK_AVAILABLE",
            "reason": "Synthetic test-only readiness, never editorial", "editorialOutcomeVerified": False,
            "publicationPermissionGranted": False, "evidence": {
                "dependencies": {"googlenewsdecoder": "0.2.1", "selectolax": "0.4.12"},
                "model": capability.MODEL, "modelDigest": "a" * 64, "syntheticContractPassed": True,
                "syntheticPromptSHA256": capability.hashlib.sha256(capability.SYNTHETIC_PROMPT.encode()).hexdigest(),
            },
        }
        self.assertFalse(capability.finalize(store, state, result, ROOT / "unused-capacity.json"))
        self.assertEqual(store.read(trial.CAPACITY_PATH)["value"], BASE)
        self.assertEqual(store.capacity_writes, [])

    def test_capacity_race_before_claim_rejected(self):
        store = Store(); permit = trial.eligible(ROOT, store, EIC, NOW)
        store.rows[trial.CAPACITY_PATH]["sha"] = "concurrent-new-sha"
        with self.assertRaises(trial.ProbeFailure):
            trial.claim(ROOT, store, permit, assignment(permit), EIC, NOW)

    def test_timeout_preserves_failed_capacity_and_spent_claim(self):
        store = Store(); state = claimed(store)
        self.assertFalse(trial.finish(ROOT, store, state, None, CHILD, NOW + timedelta(minutes=21), engine=LOCAL_ENGINE))
        self.assertEqual(store.capacity_writes, [])
        self.assertFalse(trial.eligible(ROOT, store, EIC, NOW + timedelta(minutes=21))["eligible"])

    def test_verified_shape_flags_alone_do_not_pass_canonical_gate(self):
        store = Store(); state = claimed(store)
        bad = new_draft(); bad["articles"][0]["body"] = "fake short body"
        with self.assertRaises(trial.ProbeFailure):
            trial.stamp_draft(ROOT, store, state, bad, CHILD, NOW, engine=LOCAL_ENGINE)

    def test_short_body_cannot_clear_capacity_even_with_canonical_article_shape(self):
        store = Store(); state = claimed(store)
        bad = new_draft(); bad["articles"][0]["body"] = "中" * 47 + "\n\n" + "文" * 48
        self.assertFalse(trial.canonical_article_ok(bad["articles"][0], state["claim"], NOW))
        with self.assertRaises(trial.ProbeFailure):
            trial.stamp_draft(ROOT, store, state, bad, CHILD, NOW, engine=LOCAL_ENGINE)
        self.assertEqual(store.capacity_writes, [])

    def test_previous_hkt_day_within_thirty_hours_uses_actual_canonical_policy(self):
        store = Store(); state = claimed(store)
        draft = new_draft()
        article = draft["articles"][0]
        article["publishedAt"] = trial.iso(NOW - timedelta(hours=1))
        # NOW is 00:20 HKT: the publication timestamp is on the prior local day.
        self.assertNotEqual(producer.parse_iso(article["publishedAt"]).astimezone(producer.HKT).date(),
                            NOW.astimezone(producer.HKT).date())
        self.assertTrue(trial.canonical_article_ok(article, state["claim"], NOW))
        stamped = trial.stamp_draft(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE)
        self.assertEqual(stamped["articles"][0]["publishedAt"], article["publishedAt"])

    def test_actual_canonical_policy_keeps_expired_and_future_candidates_closed(self):
        for offset in (timedelta(hours=-31), timedelta(minutes=11)):
            with self.subTest(offset=offset):
                store = Store(); state = claimed(store)
                draft = new_draft()
                draft["articles"][0]["publishedAt"] = trial.iso(NOW + offset)
                self.assertFalse(trial.canonical_article_ok(draft["articles"][0], state["claim"], NOW))
                with self.assertRaises(trial.ProbeFailure):
                    trial.stamp_draft(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE)

    def test_reviewed_trial_preserves_prior_audit_without_inheriting_normal_retry_budget(self):
        row = {"robot": "general-producer", "workflow": "general-news-producer.yml",
               "status": "reviewed-editorial-trial", "dispatchable": True, "mode": "normal",
               "dispatchInputs": {"editorial_trial_contract": trial.CONTRACT_REVISION},
               "reason": "Reviewed structured-copy behavior"}
        previous = {
            "cycleId": "prior-normal-path", "checkedAt": trial.iso(NOW - timedelta(hours=1)),
            "assignments": [{"robot": "general-producer", "workflow": row["workflow"],
                             "attempt": 2, "mode": "normal", "maxRuntimeMinutes": 15,
                             "outcomeBefore": {"prepublishDraftId": "unchanged"}}],
            "execution": [{"workflow": row["workflow"], "dispatched": True}],
        }
        snapshot = {"prepublishDraftId": "unchanged"}
        robots = {"general-producer": {"modes": ["normal"], "maxRuntimeMinutes": 15}}
        control.apply_previous_outcomes([row], robots, previous, snapshot,
                                        now=NOW, trigger_robot="general-producer")
        self.assertEqual(row["status"], "reviewed-editorial-trial")
        self.assertIs(row["dispatchable"], True)
        self.assertEqual(row["attempt"], 1)
        self.assertEqual(row["outcomeBefore"], snapshot)
        self.assertEqual(row["previousOutcome"]["attempt"], 2)
        self.assertIs(row["previousOutcome"]["progress"], False)
        self.assertEqual(row["previousOutcome"]["evaluation"],
                         "reviewed-semantic-trial-separate-from-prior-path")
        # The ordinary path's existing identical-retry guard remains intact.
        normal = copy.deepcopy(row)
        normal.update(status="assigned", dispatchable=True)
        control.apply_previous_outcomes([normal], robots, previous, snapshot,
                                        now=NOW, trigger_robot="general-producer")
        self.assertEqual(normal["status"], "stuck")
        self.assertIs(normal["dispatchable"], False)
        self.assertEqual(normal["attempt"], 3)

    def test_actual_classifier_admits_only_fresh_eic_permit_and_keeps_capacity_failed(self):
        permit = trial.eligible(ROOT, Store(), EIC, NOW)
        result = classified_trial(permit)
        row = next(row for row in result["assignments"] if row["robot"] == "general-producer")
        self.assertEqual(row["status"], "reviewed-editorial-trial")
        self.assertIs(row["dispatchable"], True)
        self.assertEqual(row["attempt"], 1)
        self.assertEqual(row["dispatchInputs"]["editorial_trial_contract"], trial.CONTRACT_REVISION)
        self.assertIs(result["evidenceSnapshot"]["producerCapacityBlocked"], True)
        self.assertEqual(result["evidenceSnapshot"]["producerCapacityStatus"], "LOCAL_FALLBACK_FAILED")
        self.assertIs(result["healthy"], False)

    def test_actual_classifier_never_admits_forged_expired_or_runtime_ready_permit(self):
        permit = trial.eligible(ROOT, Store(), EIC, NOW)
        for changed in ({}, {**permit, "publicationPermissionGranted": True},
                        {**permit, "owner": "leaf robot"}, {**permit, "contractRevision": "unreviewed"},
                        {**permit, "checkedAt": trial.iso(NOW - timedelta(minutes=6))},
                        {**permit, "checkedAt": trial.iso(NOW + timedelta(seconds=1))}):
            with self.subTest(permit=changed):
                row = next(row for row in classified_trial(changed)["assignments"]
                           if row["robot"] == "general-producer")
                self.assertIs(row["dispatchable"], False)
                self.assertNotEqual(row["status"], "reviewed-editorial-trial")

    def test_active_bound_child_is_observed_without_dispatch_retry_or_false_external_fault(self):
        store = Store(); claimed(store)
        permit = trial.eligible(ROOT, store, EIC, NOW)
        self.assertIs(permit["eligible"], False)
        self.assertIs(permit["pending"], True)
        self.assertEqual(permit["reason"], "semantic-trial-budget-consumed")
        result = classified_trial(permit)
        row = next(row for row in result["assignments"] if row["robot"] == "general-producer")
        self.assertEqual(row["status"], "awaiting-reviewed-editorial-trial-outcome")
        self.assertIs(row["dispatchable"], False)
        self.assertIs(row["requiresEditorReplan"], False)
        self.assertIs(row["requiresExternalPublisher"], False)
        self.assertNotIn("dispatchInputs", row)
        self.assertNotIn("attempt", row)
        self.assertIs(result["externalPublisherNoProgress"], False)
        self.assertIs(result["evidenceSnapshot"]["externalPublisherNoProgress"], False)
        self.assertIs(result["evidenceSnapshot"]["producerCapacityBlocked"], True)
        self.assertIs(result["healthy"], False)
        self.assertEqual(store.capacity_writes, [])

    def test_observer_clock_and_ownership_cannot_turn_invalid_proof_into_pending(self):
        store = Store(); claimed(store)
        permit = trial.eligible(ROOT, store, EIC, NOW)
        for delta in ({"trialExpiresAt": trial.iso(NOW - timedelta(seconds=1))},
                      {"checkedAt": trial.iso(NOW + timedelta(seconds=1))},
                      {"trialExpiresAt": trial.iso(NOW + timedelta(minutes=21))},
                      {"trialClaimSHA": ""}, {"trialRunAttempt": True},
                      {"trialChildStatus": "completed"}, {"publicationPermissionGranted": True},
                      {"eligible": True}, {"owner": "leaf robot"}):
            with self.subTest(delta=delta):
                result = classified_trial({**permit, **delta})
                row = next(row for row in result["assignments"] if row["robot"] == "general-producer")
                self.assertNotEqual(row["status"], "awaiting-reviewed-editorial-trial-outcome")
                self.assertFalse(row["dispatchable"])
                self.assertFalse(result["healthy"])

    def test_reused_pending_draft_and_no_candidates_cannot_clear(self):
        for draft in (None, {"status": "NO_PUBLISHABLE_UPDATE", "articles": []}):
            store = Store(); state = claimed(store)
            self.assertFalse(trial.finish(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE))
            self.assertEqual(store.capacity_writes, [])

    def test_reused_draft_identity_rejected(self):
        store = Store(); state = claimed(store)
        draft = new_draft(); draft["draftId"] = "old-draft"
        with self.assertRaises(trial.ProbeFailure):
            trial.stamp_draft(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE)

    def test_unpersisted_new_draft_cannot_clear_capacity(self):
        store = Store(); state = claimed(store)
        draft = trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW, engine=LOCAL_ENGINE)
        self.assertFalse(trial.finish(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE))
        self.assertEqual(store.capacity_writes, [])

    def test_other_child_draft_cannot_satisfy_proof(self):
        store = Store(); state = claimed(store)
        draft = trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW, engine=LOCAL_ENGINE)
        draft["eicEditorialTrial"]["childRunId"] = "concurrent-child"
        store.rows[trial.DRAFT_PATH] = {"sha": "new-draft", "value": copy.deepcopy(draft)}
        self.assertFalse(trial.finish(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE))
        self.assertEqual(store.capacity_writes, [])

    def test_exact_persisted_canonical_new_draft_allows_single_cas(self):
        store = Store(); state = claimed(store)
        draft = trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW, engine=LOCAL_ENGINE)
        store.rows[trial.DRAFT_PATH] = {"sha": "actual-new-draft-sha", "value": copy.deepcopy(draft)}
        self.assertTrue(trial.finish(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE))
        self.assertEqual(len(store.capacity_writes), 1)
        self.assertEqual(store.capacity_writes[0]["status"], "DEGRADED_LOCAL_FALLBACK")
        self.assertTrue(store.capacity_writes[0]["editorialOutcomeVerified"])
        self.assertEqual(store.capacity_writes[0]["verifiedDraftSHA"], "actual-new-draft-sha")
        self.assertEqual(store.read(trial.record_path("claim"))["value"]["priorCapacity"], BASE)

    def test_copilot_success_is_not_misreported_as_local_schema_trial_success(self):
        store = Store(); state = claimed(store)
        draft = trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW, engine=COPILOT_ENGINE)
        store.rows[trial.DRAFT_PATH] = {"sha": "copilot-draft-sha", "value": copy.deepcopy(draft)}
        self.assertTrue(trial.finish(ROOT, store, state, draft, CHILD, NOW, engine=COPILOT_ENGINE))
        capacity = store.capacity_writes[0]
        self.assertEqual(capacity["status"], "AVAILABLE")
        self.assertEqual(capacity["verifiedEngine"], "COPILOT")
        self.assertIsNone(capacity["localFallbackModel"])
        self.assertIs(capacity["structuredCopyPathSkipped"], True)
        result = store.read(trial.record_path("result"))["value"]
        self.assertEqual(result["verifiedEngine"], "COPILOT")
        self.assertIs(result["structuredCopyPathSkipped"], True)
        self.assertFalse(trial.eligible(ROOT, store, EIC, NOW)["eligible"])

    def test_missing_or_conflicting_engine_step_outputs_are_closed(self):
        for outputs in (("", "", ""), ("true", "false", "false"),
                        ("true", "true", "true"), ("unknown", "false", "true")):
            with self.subTest(outputs=outputs), self.assertRaises(trial.ProbeFailure):
                trial.producer_engine(*outputs)
        store = Store(); state = claimed(store)
        with self.assertRaises(trial.ProbeFailure):
            trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW)
        self.assertFalse(trial.finish(ROOT, store, state, new_draft(), CHILD, NOW))
        self.assertEqual(store.capacity_writes, [])

    def test_engine_switch_between_stamp_and_finish_preserves_failed_capacity(self):
        store = Store(); state = claimed(store)
        draft = trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW, engine=LOCAL_ENGINE)
        store.rows[trial.DRAFT_PATH] = {"sha": "new-draft", "value": copy.deepcopy(draft)}
        self.assertFalse(trial.finish(ROOT, store, state, draft, CHILD, NOW, engine=COPILOT_ENGINE))
        self.assertEqual(store.capacity_writes, [])

    def test_forged_engine_provenance_cannot_clear_failed_capacity(self):
        for engine in ({**LOCAL_ENGINE, "verifiedEngine": "COPILOT"},
                       {**LOCAL_ENGINE, "localFallbackSucceeded": 1},
                       {**LOCAL_ENGINE, "publicationPermissionGranted": True}):
            with self.subTest(engine=engine):
                store = Store(); state = claimed(store)
                with self.assertRaises(trial.ProbeFailure):
                    trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW, engine=engine)
                self.assertFalse(trial.finish(ROOT, store, state, new_draft(), CHILD, NOW, engine=engine))
                self.assertEqual(store.capacity_writes, [])

    def test_cas_race_never_overwrites_newer_capacity(self):
        store = Store(); state = claimed(store)
        draft = trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW, engine=LOCAL_ENGINE)
        store.rows[trial.DRAFT_PATH] = {"sha": "new-draft", "value": copy.deepcopy(draft)}
        store.rows[trial.CAPACITY_PATH]["sha"] = "other-producer-update"
        self.assertFalse(trial.finish(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE))
        self.assertEqual(store.capacity_writes, [])

    def test_result_write_failure_still_permanently_spends_claim(self):
        store = Store(); state = claimed(store)
        with patch.object(store, "create", side_effect=trial.ProbeFailure("store", "unavailable")):
            with self.assertRaises(trial.ProbeFailure):
                trial.finish(ROOT, store, state, None, CHILD, NOW, engine=LOCAL_ENGINE)
        self.assertFalse(trial.eligible(ROOT, store, EIC, NOW)["eligible"])
        self.assertEqual(store.capacity_writes, [])

    def test_draft_replaced_while_recording_proof_never_clears_capacity(self):
        store = Store(); state = claimed(store)
        draft = trial.stamp_draft(ROOT, store, state, new_draft(), CHILD, NOW, engine=LOCAL_ENGINE)
        store.rows[trial.DRAFT_PATH] = {"sha": "new-draft", "value": copy.deepcopy(draft)}
        original_create = store.create
        def replaced(path, value):
            original_create(path, value)
            if path == trial.record_path("result"):
                store.rows[trial.DRAFT_PATH] = {"sha": "different-producer", "value": {"draftId": "other"}}
        with patch.object(store, "create", side_effect=replaced):
            self.assertFalse(trial.finish(ROOT, store, state, draft, CHILD, NOW, engine=LOCAL_ENGINE))
        self.assertEqual(store.capacity_writes, [])

    def test_workflow_hooks_preserve_owner_order_and_hold(self):
        assignment_text = (ROOT / ".github/workflows/editor-in-chief-newsroom-assignment.yml").read_text(encoding="utf-8")
        producer_text = (ROOT / ".github/workflows/general-news-producer.yml").read_text(encoding="utf-8")
        self.assertLess(assignment_text.index('reason":"already-active'), assignment_text.index('editorial_revision_trial.py claim'))
        self.assertLess(assignment_text.index('editorial_revision_trial.py claim'), assignment_text.index('if gh "${args[@]}"'))
        self.assertLess(producer_text.index('editorial_revision_trial.py bind'), producer_text.index('Load the latest discovery reservoir'))
        self.assertEqual(producer_text.count("steps.trial_guard.outputs.active != 'true'"), 2)
        self.assertIn("/tmp/eic-editorial-reviewed/scripts/editorial_revision_trial.py finish", producer_text)
        self.assertLess(producer_text.index('Persist the verified draft'), producer_text.index('Finalize reviewed trial'))
        self.assertIn("remaining=min(600, math.floor(deadline-time.time()))", producer_text)
        self.assertIn('timeout --signal=KILL "${fallback_seconds}s"', producer_text)
        self.assertIn("--deadline-unix '${{ steps.trial_guard.outputs.fallback_deadline_unix }}'", producer_text)
        self.assertLess(producer_text.index('timeout --signal=KILL'), producer_text.index('GENERAL_NEWS_LOCAL_CAPACITY_FALLBACK_OK'))
        self.assertIn('scripts/editorial_trial_observation.py', assignment_text)
        module_text = (ROOT / "scripts/editorial_revision_trial.py").read_text(encoding="utf-8")
        self.assertNotIn("force", module_text)
        self.assertNotIn("Newsroom Publisher", module_text)
        self.assertNotIn("ollama_json(", module_text)


if __name__ == "__main__":
    unittest.main()
