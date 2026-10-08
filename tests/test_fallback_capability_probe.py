#!/usr/bin/env python3
"""All capability tests use fake stores/local model responses; no GitHub writes."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
import sys
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
PROBE_PATH = ROOT / "scripts/probe_general_news_fallback_capability.py"
spec = importlib.util.spec_from_file_location("capability_probe", PROBE_PATH)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
OLD_WORKFLOW_BLOB = "fcdfc29ba29ef57be3ff2f9dd795c9649bd3fcc8"


def evidence():
    return {
        "dependencies": {"googlenewsdecoder": "0.2.1", "selectolax": "0.4.12"},
        "model": probe.MODEL, "modelDigest": "a" * 64,
        "syntheticPromptSHA256": hashlib.sha256(probe.SYNTHETIC_PROMPT.encode()).hexdigest(),
        "syntheticContractPassed": True,
    }


class MemoryStore:
    def __init__(self):
        self.ledger = {}
        self.capacity = {
            "sha": "old-capacity-sha",
            "value": {
                "status": "LOCAL_FALLBACK_FAILED",
                "checkedAt": "2026-10-07T12:17:33.596598Z",
                "reason": "Original decoder import error and Copilot quota exhausted",
                "workflowRunId": "37619701121",
            },
        }
        self.ready = True
        self.cas_calls = 0

    def ledger_ready(self):
        return self.ready

    def read(self, path):
        value = self.capacity if path == probe.CAPACITY_PATH else self.ledger.get(path)
        return copy.deepcopy(value)

    def create(self, path, value):
        if path in self.ledger:
            raise probe.ProbeFailure("store", "http-422")
        self.ledger[path] = {"sha": "immutable-ledger-sha", "value": copy.deepcopy(value)}

    def compare_and_swap_capacity(self, expected_sha, value):
        self.cas_calls += 1
        if self.capacity is None or self.capacity["sha"] != expected_sha:
            return False
        self.capacity = {"sha": "new-capacity-sha", "value": copy.deepcopy(value)}
        return True


class CapabilityProbeTests(unittest.TestCase):
    def claimed(self, td):
        store = MemoryStore()
        path = Path(td) / "claim.json"
        result = probe.prepare(ROOT, store, path)
        self.assertTrue(result["claimed"])
        return store, probe.load_json(path)

    def good_result(self, state):
        return probe.run_probe(
            ROOT, state, bootstrap=lambda *args: None, checker=lambda *args: evidence()
        )

    def test_exact_reviewed_revision_matches_current_fix(self):
        self.assertEqual(probe.revision(ROOT), probe.REVIEWED_REVISION)

    def test_news_content_and_main_head_do_not_change_probe_revision(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in probe.REVISION_FILES:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes((ROOT / name).read_bytes())
            original = probe.revision(root)
            (root / "data").mkdir()
            (root / "data/live.json").write_text('{"updated":"new article"}', encoding="utf-8")
            (root / "HEAD").write_text("different-main-head", encoding="utf-8")
            self.assertEqual(probe.revision(root), original)

    def test_unreviewed_revision_cannot_claim_or_run(self):
        store = MemoryStore()
        with tempfile.TemporaryDirectory() as td, patch.object(probe, "revision", return_value="b" * 64):
            planned = probe.prepare(ROOT, store, Path(td) / "claim.json")
            self.assertFalse(planned["claimed"])
            self.assertEqual(store.ledger, {})

    def test_missing_isolated_ledger_fails_closed(self):
        store = MemoryStore()
        store.ready = False
        with tempfile.TemporaryDirectory() as td:
            planned = probe.prepare(ROOT, store, Path(td) / "claim.json")
            self.assertFalse(planned["claimed"])
            self.assertIn("not-provisioned", planned["reason"])
        self.assertEqual(store.ledger, {})

    def test_immutable_claim_preserves_original_error_and_spends_attempt_first(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            self.assertEqual(state["priorCapacity"], store.capacity["value"])
            self.assertEqual(state["remainingAttempts"], 0)
            self.assertEqual(store.ledger[probe.claim_path(probe.REVIEWED_REVISION)]["value"], state)
            planned = probe.prepare(ROOT, store, Path(td) / "second.json")
            self.assertFalse(planned["claimed"])
            self.assertIn("already-consumed", planned["reason"])

    def test_shared_publication_branch_replacement_does_not_reset_budget(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            store.capacity = MemoryStore().capacity  # emulate prepublish-news replaced
            planned = probe.prepare(ROOT, store, Path(td) / "second.json")
            self.assertFalse(planned["claimed"])
            self.assertEqual(len(store.ledger), 1)

    def test_prepare_race_never_starts_runtime_without_accepted_claim(self):
        store = MemoryStore()
        with tempfile.TemporaryDirectory() as td, patch.object(
            store, "create", side_effect=probe.ProbeFailure("store", "http-422")
        ):
            path = Path(td) / "claim.json"
            with self.assertRaises(probe.ProbeFailure):
                probe.prepare(ROOT, store, path)
            self.assertFalse(path.exists())

    def test_failure_consumes_budget_and_stays_failed(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            def fail(*args):
                raise probe.ProbeFailure("dependencies", "incompatible")
            bootstrap = Mock(side_effect=fail)
            result = probe.run_probe(ROOT, state, bootstrap=bootstrap, checker=Mock())
            self.assertEqual(result["status"], "LOCAL_FALLBACK_FAILED")
            bootstrap.assert_called_once()
            self.assertTrue(probe.finalize(store, state, result, Path(td) / "capacity.json"))
            self.assertFalse(probe.prepare(ROOT, store, Path(td) / "retry.json")["claimed"])
            self.assertEqual(store.capacity["value"]["remainingProbeAttempts"], 0)

    def test_timeout_does_not_leak_error_or_token(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            result = probe.run_probe(
                ROOT, state, bootstrap=lambda *args: None,
                checker=Mock(side_effect=TimeoutError("secret-token-value")),
            )
            self.assertEqual(result["status"], "LOCAL_FALLBACK_FAILED")
            self.assertNotIn("secret-token-value", json.dumps(result))
            self.assertEqual(result["failure"]["code"], "TimeoutError")

    def test_success_is_runtime_only_and_preserves_immutable_old_failure(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            result = self.good_result(state)
            self.assertEqual(result["status"], "LOCAL_FALLBACK_AVAILABLE")
            self.assertTrue(probe.finalize(store, state, result, Path(td) / "capacity.json"))
            capacity = store.capacity["value"]
            self.assertIs(capacity["editorialOutcomeVerified"], False)
            self.assertIs(capacity["publicationPermissionGranted"], False)
            self.assertTrue(capacity["capabilityOnly"])
            self.assertEqual(capacity["probeLedgerBranch"], probe.LEDGER_BRANCH)
            self.assertEqual(
                store.ledger[probe.claim_path(probe.REVIEWED_REVISION)]["value"]["priorCapacity"],
                state["priorCapacity"],
            )
            self.assertNotIn("previousCapacity", capacity)

    def test_newer_production_failure_cannot_be_overwritten_by_stale_available(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            result = self.good_result(state)
            newer = {"sha": "newer-production-sha", "value": {"status": "LOCAL_FALLBACK_FAILED", "checkedAt": "newer"}}
            store.capacity = copy.deepcopy(newer)
            destination = Path(td) / "capacity.json"
            self.assertFalse(probe.finalize(store, state, result, destination))
            self.assertEqual(store.capacity, newer)
            self.assertFalse(destination.exists())
            self.assertIn(probe.result_path(probe.REVIEWED_REVISION), store.ledger)

    def test_available_requires_all_exact_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            result = self.good_result(state)
            result["evidence"]["syntheticContractPassed"] = False
            with self.assertRaises(probe.ProbeFailure):
                probe.finalize(store, state, result, Path(td) / "capacity.json")
            self.assertEqual(store.cas_calls, 0)

    def test_malformed_runtime_metadata_is_rejected_before_result_or_cas(self):
        mutations = (
            ("schemaVersion", True), ("schemaVersion", 2),
            ("owner", "leaf producer"), ("scope", "news"),
            ("attempt", True), ("remainingAttempts", False),
            ("checkedAt", None), ("checkedAt", "bad"),
            ("checkedAt", "2026-10-08T11:00:00"),
            ("checkedAt", "2026-10-08T19:00:00+08:00"),
            ("reason", ""), ("reason", {"misleading": "value"}),
        )
        for key, value in mutations:
            with self.subTest(key=key, value=value), tempfile.TemporaryDirectory() as td:
                store, state = self.claimed(td)
                result = self.good_result(state)
                result[key] = value
                with self.assertRaises(probe.ProbeFailure):
                    probe.finalize(store, state, result, Path(td) / "capacity.json")
                self.assertEqual(store.cas_calls, 0)
                self.assertNotIn(probe.result_path(probe.REVIEWED_REVISION), store.ledger)

    def test_result_time_must_follow_claim_and_not_be_future_dated(self):
        for timestamp in (
            "2026-01-01T00:00:00Z",
            (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        ):
            with self.subTest(timestamp=timestamp), tempfile.TemporaryDirectory() as td:
                store, state = self.claimed(td)
                result = self.good_result(state)
                result["checkedAt"] = timestamp
                with self.assertRaises(probe.ProbeFailure):
                    probe.finalize(store, state, result, Path(td) / "capacity.json")
                self.assertEqual(store.cas_calls, 0)
                self.assertNotIn(probe.result_path(probe.REVIEWED_REVISION), store.ledger)

    def test_invalid_checker_evidence_never_reports_available(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            result = probe.run_probe(
                ROOT, state, bootstrap=lambda *args: None, checker=lambda *args: {}
            )
            self.assertEqual(result["status"], "LOCAL_FALLBACK_FAILED")
            self.assertNotIn("evidence", result)
            self.assertTrue(probe.finalize(store, state, result, Path(td) / "capacity.json"))
            self.assertEqual(store.capacity["value"]["status"], "LOCAL_FALLBACK_FAILED")

    def test_failed_result_requires_redacted_failure_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            result = self.good_result(state)
            result["status"] = "LOCAL_FALLBACK_FAILED"
            with self.assertRaises(probe.ProbeFailure):
                probe.finalize(store, state, result, Path(td) / "capacity.json")
            self.assertEqual(store.cas_calls, 0)

    def test_interrupted_workflow_records_failure_without_reclaiming_budget(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            destination = Path(td) / "capacity.json"
            argv = [
                "probe", "finalize", "--state", str(Path(td) / "claim.json"),
                "--result", str(Path(td) / "never-created-result.json"),
                "--capacity", str(destination),
            ]
            with patch.object(sys, "argv", argv), patch.object(
                probe, "GitHubCapacityStore", return_value=store
            ), patch("builtins.print"):
                self.assertEqual(probe.main(), 0)
            result = store.ledger[probe.result_path(probe.REVIEWED_REVISION)]["value"]
            self.assertEqual(result["status"], "LOCAL_FALLBACK_FAILED")
            self.assertEqual(result["failure"]["code"], "interrupted")
            self.assertEqual(result["scope"], probe.PROBE_SCOPE)
            self.assertEqual(probe.load_json(destination)["remainingProbeAttempts"], 0)
            self.assertFalse(probe.prepare(ROOT, store, Path(td) / "retry.json")["claimed"])

    def test_actual_contents_api_capacity_cas_conflict_is_not_retried(self):
        store = probe.GitHubCapacityStore("never-used-test-token", probe.REPOSITORY)
        with patch.object(store, "read", return_value={"sha": "expected", "value": {}}), patch.object(
            store, "json_request", side_effect=probe.ProbeFailure("store", "http-409")
        ) as request:
            self.assertFalse(store.compare_and_swap_capacity("expected", {"status": "LOCAL_FALLBACK_AVAILABLE"}))
            self.assertEqual(request.call_count, 1)

    def test_claim_and_result_are_create_only(self):
        with tempfile.TemporaryDirectory() as td:
            store, state = self.claimed(td)
            result = self.good_result(state)
            probe.finalize(store, state, result, Path(td) / "capacity.json")
            original = copy.deepcopy(store.ledger)
            with self.assertRaises(probe.ProbeFailure):
                probe.finalize(store, state, result, Path(td) / "second.json")
            self.assertEqual(store.ledger, original)

    def fake_dependency_loader(self):
        module = types.SimpleNamespace(check_dependencies=lambda: evidence()["dependencies"])
        return patch.object(probe.importlib.util, "spec_from_file_location", return_value=types.SimpleNamespace(loader=Mock())), patch.object(
            probe.importlib.util, "module_from_spec", return_value=module
        )

    def test_model_check_uses_only_fixed_non_news_synthetic_prompt(self):
        first, second = self.fake_dependency_loader()
        calls = []
        def local(endpoint, **kwargs):
            calls.append((endpoint, kwargs))
            if endpoint == "/api/tags":
                return {"models": [{"name": probe.MODEL, "digest": "a" * 64}]}
            return {"model": probe.MODEL, "done": True, "response": json.dumps(probe.EXPECTED_SYNTHETIC)}
        with first, second, patch.object(probe, "local_json", side_effect=local):
            found = probe.check_runtime(ROOT, probe.time.monotonic() + 60)
        self.assertEqual(found, evidence())
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][1]["payload"]["prompt"], probe.SYNTHETIC_PROMPT)
        self.assertEqual(calls[1][1]["payload"]["keep_alive"], 0)

    def test_model_missing_rejects_before_generation(self):
        first, second = self.fake_dependency_loader()
        with first, second, patch.object(probe, "local_json", return_value={"models": []}) as calls:
            with self.assertRaises(probe.ProbeFailure):
                probe.check_runtime(ROOT, probe.time.monotonic() + 60)
            self.assertEqual(calls.call_count, 1)

    def test_malformed_synthetic_response_fails_closed(self):
        first, second = self.fake_dependency_loader()
        with first, second, patch.object(probe, "local_json", side_effect=[
            {"models": [{"name": probe.MODEL, "digest": "a" * 64}]},
            {"model": probe.MODEL, "done": True, "response": '{"readiness":"ok","value":true}'},
        ]):
            with self.assertRaises(probe.ProbeFailure):
                probe.check_runtime(ROOT, probe.time.monotonic() + 60)

    def test_credentials_not_forwarded_to_runtime_child(self):
        with patch.dict(probe.os.environ, {"GH_TOKEN": "secret", "GITHUB_TOKEN": "secret", "MY_API_KEY": "secret", "PATH": "safe"}):
            child = probe.clean_child_env()
            self.assertNotIn("GH_TOKEN", child)
            self.assertNotIn("GITHUB_TOKEN", child)
            self.assertNotIn("MY_API_KEY", child)
            self.assertEqual(child["PATH"], "safe")

    def test_store_only_allows_isolated_telemetry_paths_and_branches(self):
        store = probe.GitHubCapacityStore("never-used-test-token", probe.REPOSITORY)
        self.assertFalse(store.allowed_path("data/live.json"))
        self.assertFalse(store.allowed_path("data/prepublish.json"))
        self.assertTrue(store.allowed_path(probe.claim_path(probe.REVIEWED_REVISION)))
        with patch.object(store, "json_request", return_value={}) as network:
            store.request("GET", probe.claim_path(probe.REVIEWED_REVISION))
            request = network.call_args.args[0]
            self.assertIn("?ref=" + probe.LEDGER_BRANCH, request.full_url)
            with self.assertRaises(probe.ProbeFailure):
                store.request("PUT", probe.claim_path(probe.REVIEWED_REVISION), {"branch": probe.CAPACITY_BRANCH})
            with self.assertRaises(probe.ProbeFailure):
                store.request("PUT", "data/live.json", {"branch": "main"})

    def test_no_leaf_dispatch_or_content_producer_invocation(self):
        source = PROBE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("/actions/", source)
        self.assertNotIn("gh workflow", source)
        self.assertNotIn("general_news_local_fallback.main", source)
        self.assertNotIn("data/live.json", source)
        self.assertNotIn("data/prepublish.json", source)

    def test_existing_classification_dispatch_and_gates_unchanged(self):
        workflow = (ROOT / ".github/workflows/editor-in-chief-newsroom-assignment.yml").read_text(encoding="utf-8")
        start = workflow.index("      # Infrastructure only: one immutable attempt")
        end = workflow.index("      - name: Run current newsroom checks", start)
        restored = workflow[:start] + workflow[end:]
        for path in (
            "scripts/requirements-general-news-fallback.txt",
            "scripts/check_general_news_fallback_dependencies.py",
            "scripts/probe_general_news_fallback_capability.py",
        ):
            restored = restored.replace('      - "' + path + '"\n', "")
        restored = restored.replace(
            "    # Existing control plane plus at most one bounded runtime capability check.\n    timeout-minutes: 12\n",
            "    timeout-minutes: 8\n",
        )
        raw = restored.encode("utf-8")
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        self.assertEqual(blob, OLD_WORKFLOW_BLOB)


if __name__ == "__main__":
    unittest.main()
