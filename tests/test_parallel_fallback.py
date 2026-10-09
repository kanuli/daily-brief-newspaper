"""Synthetic parallel binding/budget checks; no external or publication writes."""
import contextlib
import copy
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import test_source_selection_budget as budget
sys.path.insert(0, str(budget.ROOT / "scripts"))
import parallel_general_news_fallback as parallel
import editorial_revision_trial as trial

CODE = "a" * 40
RUN = "901"


def make_plan(request, staging=None, state=None, now=1000):
    staging = {} if staging is None else staging
    return {"schemaVersion": 1, "runId": RUN, "codeSHA": CODE,
            "requestDigest": parallel.digest(request), "stagingDigest": parallel.digest(staging),
            "stateDigest": parallel.digest(state), "createdUnix": now,
            "absoluteDeadlineUnix": now + 660, "deadlineUnix": now + 600,
            "active": state is not None, "workerCount": 3,
            "maxSourceProbesPerWorker": 4, "maxModelCallsPerWorker": 1}


def fragment(plan, index, row):
    return {"worker": index, "planDigest": parallel.digest(plan), "model": parallel.MODEL, "ok": True,
            "facts": {"verified": [{"candidateId": row["id"], "desk": row["desk"], "sourceEvidence": []}]},
            "copies": {"articles": [{"candidateId": row["id"], "verifiedCopy": {}}]}}


class ParallelTests(unittest.TestCase):
    def setUp(self):
        self.request = budget.request()
        self.plan = make_plan(self.request)

    def test_partitions_are_disjoint_and_cover_all_original_candidates_without_edits(self):
        before = copy.deepcopy(self.request)
        shards = [parallel.partition(self.request, i) for i in range(3)]
        ids = [row["id"] for shard in shards for row in shard["candidates"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {row["id"] for row in self.request["candidates"]})
        self.assertEqual(self.request, before)
        for i, shard in enumerate(shards):
            self.assertEqual(shard["staleDesks"], self.request["staleDesks"][i::3])

    def test_partition_rejects_duplicate_desks_candidates_and_cross_desk_ambiguity(self):
        for kind in ("desk", "candidate", "other-desk", "empty-id", "non-object"):
            request = copy.deepcopy(self.request)
            if kind == "desk": request["staleDesks"].append(request["staleDesks"][0])
            elif kind == "candidate": request["candidates"].append(request["candidates"][0])
            elif kind == "other-desk": request["candidates"][0]["desk"] = "unassigned"
            elif kind == "empty-id": request["candidates"][0]["id"] = ""
            else: request["candidates"][0] = []
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                parallel.partition(request, 0)

    def test_invalid_worker_indices_include_booleans(self):
        for i in (-1, 3, True, False, "0", 0.0):
            with self.subTest(index=i), self.assertRaises(ValueError):
                parallel.partition(self.request, i)

    def test_fixed_plan_accepts_generation_inside_deadline(self):
        parallel.check_plan(self.plan, self.request, {}, None, RUN, CODE, 1200, generation=True)

    def test_any_binding_budget_or_clock_mutation_is_closed(self):
        changes = {"runId": "other", "codeSHA": "b" * 40, "requestDigest": "other",
                   "stagingDigest": "other", "stateDigest": "other", "workerCount": 4,
                   "maxSourceProbesPerWorker": 5, "maxModelCallsPerWorker": 2, "active": "false",
                   "createdUnix": 1300, "absoluteDeadlineUnix": 2000,
                   "deadlineUnix": 1601, "schemaVersion": True}
        for key, value in changes.items():
            plan = {**self.plan, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError):
                parallel.check_plan(plan, self.request, {}, None, RUN, CODE, 1200, generation=True)

    def test_nan_infinite_boolean_and_stale_clock_rejected(self):
        for key in ("createdUnix", "absoluteDeadlineUnix", "deadlineUnix"):
            for value in (math.nan, math.inf, -math.inf, True, None, "1000"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    parallel.check_plan({**self.plan, key: value}, self.request, {}, None, RUN, CODE, 1200)
        with self.assertRaises(ValueError):
            parallel.check_plan(self.plan, self.request, {}, None, RUN, CODE, 2201)

    def test_generation_expiry_cannot_be_renewed_by_worker_start(self):
        for now in (1600, 1601, 1700):
            with self.subTest(now=now), self.assertRaisesRegex(ValueError, "shared-deadline-expired"):
                parallel.check_plan(self.plan, self.request, {}, None, RUN, CODE, now, generation=True)
        # Persistence and failure accounting still have their existing lease.
        parallel.check_plan(self.plan, self.request, {}, None, RUN, CODE, 1700)

    def test_active_trial_deadline_must_equal_immutable_bind_plus_660(self):
        state = {"claim": {"contractRevision": trial.CONTRACT_REVISION},
                 "run": {"childRunId": RUN, "boundAt": "1970-01-01T00:16:40Z"}}
        plan = make_plan(self.request, state=state)
        parallel.check_plan(plan, self.request, {}, state, RUN, CODE, 1200)
        for key, value in (("absoluteDeadlineUnix", 1659), ("active", False)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                parallel.check_plan({**plan, key: value}, self.request, {}, state, RUN, CODE, 1200)

    def test_aggregate_preserves_fragments_but_never_claims_editorial_verification(self):
        fragments = [fragment(self.plan, i, parallel.partition(self.request, i)["candidates"][0]) for i in range(3)]
        original = copy.deepcopy(fragments)
        facts, copies = parallel.collect(self.plan, self.request, fragments)
        self.assertEqual(len(copies["articles"]), 3)
        self.assertEqual(len(facts["verified"]), 3)
        self.assertEqual(fragments, original)
        # Empty copy is transported, NOT editorial acceptance; canonical merge
        # downstream must reject it. No synthesized copy, timestamps or flags.
        self.assertTrue(all(row["verifiedCopy"] == {} for row in copies["articles"]))

    def test_duplicate_worker_wrong_identity_and_other_model_are_rejected(self):
        row = parallel.partition(self.request, 0)["candidates"][0]
        good = fragment(self.plan, 0, row)
        for key, value in (("worker", True), ("worker", 3), ("planDigest", "other"),
                           ("model", "qwen2.5:7b"), ("ok", "true")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                parallel.collect(self.plan, self.request, [{**good, key: value}])
        with self.assertRaises(ValueError): parallel.collect(self.plan, self.request, [good, good])
        with self.assertRaises(ValueError): parallel.collect(self.plan, self.request, [good] * 4)

    def test_success_must_have_exactly_one_matching_assigned_candidate(self):
        good = fragment(self.plan, 0, parallel.partition(self.request, 0)["candidates"][0])
        for kind in ("two", "zero", "cross-desk", "wrong-id", "wrong-desk"):
            bad = copy.deepcopy(good)
            if kind == "two": bad["copies"]["articles"] *= 2
            elif kind == "zero": bad["facts"]["verified"] = []
            elif kind == "cross-desk":
                row = parallel.partition(self.request, 1)["candidates"][0]
                bad = fragment(self.plan, 0, row)
            elif kind == "wrong-id": bad["copies"]["articles"][0]["candidateId"] = "other"
            else: bad["facts"]["verified"][0]["desk"] = "other"
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                parallel.collect(self.plan, self.request, [bad])

    def test_failed_or_missing_workers_never_supply_publishable_copy(self):
        failed = {"worker": 0, "planDigest": parallel.digest(self.plan), "model": parallel.MODEL,
                  "ok": False, "facts": None, "copies": None}
        self.assertEqual(parallel.collect(self.plan, self.request, [failed]), ({"verified": []}, {"articles": []}))
        self.assertEqual(parallel.collect(self.plan, self.request, []), ({"verified": []}, {"articles": []}))
        with self.assertRaises(ValueError):
            parallel.collect(self.plan, self.request, [{**failed, "copies": {"articles": [{}]}}])

    def test_three_real_synthetic_worker_loops_cannot_exceed_global_source_budget(self):
        attempts, calls = [], []
        for i in range(3):
            harness = budget.SourceSelectionBudgetTests(); harness.setUp()
            harness.module.MAX_SOURCE_PROBES = 4
            harness.module.MAX_MODEL_CALLS = 1
            def missing(row, deadline):
                attempts.append((i, row["id"]))
                return harness.response({"packet": None, "diagnostic": "no-direct-source-text"})
            result = harness.run_main(parallel.partition(self.request, i), missing)
            self.assertEqual(result.writes, [])
            calls.extend(result.models)
        self.assertEqual(len(attempts), 12)
        self.assertEqual(len({cid for _, cid in attempts}), 12)
        self.assertEqual(calls, [])

    def test_rejected_model_is_still_charged_and_each_worker_cannot_retry(self):
        count = 0
        for i in range(3):
            harness = budget.SourceSelectionBudgetTests(); harness.setUp()
            harness.module.MAX_SOURCE_PROBES = 4; harness.module.MAX_MODEL_CALLS = 1
            result = harness.run_main(parallel.partition(self.request, i), harness.good_source,
                                      lambda source, options: {"candidateId": "bad"}, daily_ready=True)
            count += len(result.models)
            self.assertEqual(len(result.models), 1)
            self.assertEqual(result.writes, [])
        self.assertEqual(count, 3)

    def test_successful_workers_preserve_daily_body_and_original_editorial_gates(self):
        for i in range(3):
            harness = budget.SourceSelectionBudgetTests(); harness.setUp()
            harness.module.MAX_SOURCE_PROBES = 4; harness.module.MAX_MODEL_CALLS = 1
            result = harness.run_main(parallel.partition(self.request, i), harness.good_source, daily_ready=True)
            self.assertEqual(len(result.models), 1)
            self.assertIsNone(result.error)
            self.assertEqual(len(json.loads(result.writes[1])["articles"]), 1)

    def test_workflow_has_one_bind_three_readonly_workers_and_one_canonical_producer(self):
        text = (budget.ROOT / ".github/workflows/general-news-producer.yml").read_text(encoding="utf-8")
        self.assertEqual(text.count("editorial_revision_trial.py bind"), 1)
        self.assertEqual(text.count("general_news_verification_robot.py produce"), 1)
        self.assertIn("worker: [0, 1, 2]", text)
        self.assertIn("max-parallel: 3", text)
        self.assertIn("fail-fast: false", text)
        self.assertIn("contents: read", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("needs: [prepare, workers]", text)
        self.assertIn("if: always() && needs.prepare.result == 'success'", text)
        self.assertEqual(text.count("ref: ${{ needs.prepare.outputs.code_sha }}"), 2)
        self.assertNotIn("workflow_dispatch", text[text.index("jobs:"):])
        self.assertIn("merge-multiple: false", text)
        self.assertNotIn("overwrite:", text)
        self.assertIn("python -u scripts/parallel_general_news_fallback.py worker", text)

    def test_actual_worker_entry_strips_credentials_uses_original_daily_ready_main_and_one_call(self):
        fallback = budget.load_synthetic_module()
        models, probes = [], []
        def source(row, deadline):
            probes.append(row["id"])
            self.assertNotIn("GH_TOKEN", os.environ)
            self.assertNotIn("GITHUB_TOKEN", os.environ)
            return budget.packet(row), None
        def model(prompt, **kwargs):
            models.append(kwargs)
            packet = json.JSONDecoder().raw_decode(prompt.split("INPUT:\n", 1)[1])[0]
            return budget.structured_copy(packet)
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            plan = make_plan(self.request, now=time.time() - 1)
            for name, value in (("request", self.request), ("staging", {}), ("plan", plan)):
                parallel.write(directory / (name + ".json"), value)
            args = ["parallel", "worker", "--directory", str(directory), "--worker", "0"]
            with patch.object(sys, "argv", args), patch.dict(sys.modules, {"general_news_local_fallback": fallback}), \
                 patch.object(trial, "context", return_value={"runId": RUN}), patch.object(trial, "reviewed_code", return_value=True), \
                 patch.object(parallel.subprocess, "check_output", return_value=CODE), \
                 patch.object(fallback, "bounded_source_packet", side_effect=source), \
                 patch.object(fallback, "ollama_json", side_effect=model), \
                 patch.dict(os.environ, {"GH_TOKEN": "SYNTHETIC-SECRET", "GITHUB_TOKEN": "SYNTHETIC-SECRET"}), \
                 contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(parallel.main(), 0)
                self.assertNotIn("SYNTHETIC-SECRET", output.getvalue())
            self.assertEqual(len(models), 1)
            self.assertEqual(len(probes), 1)
            self.assertEqual(fallback.MAX_SOURCE_PROBES, 4)
            self.assertEqual(fallback.MAX_MODEL_CALLS, 1)
            pattern = models[0]["schema"]["properties"]["verifiedCopy"]["properties"]["body"]["items"]["pattern"]
            self.assertIn("{49,599}", pattern)
            result = parallel.read(directory / "fragment.json")
            self.assertTrue(result["ok"])
            self.assertEqual(result["planDigest"], parallel.digest(plan))

    def test_readonly_authorization_calls_exact_state_verifier_before_any_worker_activity(self):
        state = {"claim": {"contractRevision": trial.CONTRACT_REVISION},
                 "run": {"childRunId": RUN, "boundAt": "1970-01-01T00:16:40Z"}}
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            plan = make_plan(self.request, state=state)
            for name, value in (("request", self.request), ("staging", {}), ("plan", plan), ("state", state)):
                parallel.write(directory / (name + ".json"), value)
            args = ["parallel", "authorize", "--directory", str(directory), "--active", "true",
                    "--github-output", str(directory / "outputs")]
            with patch.object(sys, "argv", args), patch.object(trial, "context", return_value={"runId": RUN}), \
                 patch.object(trial, "reviewed_code", return_value=True), \
                 patch.object(parallel.subprocess, "check_output", return_value=CODE), \
                 patch.object(parallel.time, "time", return_value=1200), \
                 patch.object(trial, "TrialStore") as store, patch.object(trial, "verify_state") as verify:
                self.assertEqual(parallel.main(), 0)
                verify.assert_called_once()
                self.assertEqual(verify.call_args.args[2], state)
                self.assertEqual(verify.call_args.args[3], {"runId": RUN})
                store.return_value.create.assert_not_called()
                store.return_value.compare_and_swap_capacity.assert_not_called()
            self.assertIn("deadline_unix=1600", (directory / "outputs").read_text())


if __name__ == "__main__":
    unittest.main()
