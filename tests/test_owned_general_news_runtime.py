"""Synthetic-only runtime ownership tests; no daemon, inference or network."""
import copy
import json
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import owned_general_news_runtime as runtime


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.loaded = {"model": runtime.MODEL, "done": True, "response": "", "eval_count": 0}
        self.running = {"models": [{"name": runtime.MODEL, "digest": runtime.DIGEST,
                                    "size": 4000000000, "size_vram": 0, "context_length": 32768}]}
        self.calls = []

    def request(self, path, deadline, clock, payload=None):
        self.calls.append((path, deadline, copy.deepcopy(payload)))
        return copy.deepcopy(self.loaded if path == "/api/generate" else self.running)

    def test_empty_load_is_not_another_copy_call_and_both_requests_share_fixed_budget(self):
        observed = runtime.prepare(1000, clock=lambda: 100, request=self.request)
        self.assertEqual([row[1] for row in self.calls], [160, 160])
        self.assertEqual(self.calls[0][2], {"model": runtime.MODEL, "prompt": "", "stream": False,
                                          "keep_alive": "10m", "options": {"num_ctx": 32768}})
        self.assertIsNone(self.calls[1][2])
        self.assertEqual(observed, {"model": runtime.MODEL, "ownedPort": 11435, "emptyPromptLoaded": True,
                                    "size": 4000000000, "size_vram": 0, "context_length": 32768})

    def test_near_expiry_does_not_renew_child_deadline(self):
        runtime.prepare(110, clock=lambda: 100, request=self.request)
        self.assertEqual([row[1] for row in self.calls], [110, 110])

    def test_expired_or_nonfinite_deadline_never_calls_runtime(self):
        for deadline in (99, 100, math.nan, math.inf, -math.inf):
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                runtime.prepare(deadline, clock=lambda: 100, request=self.request)
        self.assertEqual(self.calls, [])

    def test_incomplete_other_model_prose_or_generation_is_rejected(self):
        for delta in ({"done": False}, {"done": "true"}, {"model": "unreviewed"},
                      {"response": "SYNTHETIC NOT NEWS"}, {"eval_count": 1}, {"eval_count": False}):
            self.loaded = {"model": runtime.MODEL, "done": True, "response": "", "eval_count": 0, **delta}
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                runtime.prepare(1000, clock=lambda: 100, request=self.request)

    def test_wrong_digest_or_unreviewed_loaded_model_or_context_is_rejected(self):
        for delta in ({"digest": "different"}, {"name": "unreviewed"},
                      {"context_length": 4096}, {"context_length": True}):
            self.running["models"][0] = {"name": runtime.MODEL, "digest": runtime.DIGEST, **delta}
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                runtime.prepare(1000, clock=lambda: 100, request=self.request)
        for models in ([], [{}, {}], [None], None):
            self.running = {"models": models}
            with self.subTest(models=models), self.assertRaises(ValueError):
                runtime.prepare(1000, clock=lambda: 100, request=self.request)

    def test_arbitrary_runtime_strings_and_extra_fields_are_not_logged(self):
        self.running["models"][0].update({"size": "PRIVATE", "size_vram": True, "prompt": "PRIVATE", "token": "PRIVATE"})
        observed = runtime.prepare(1000, clock=lambda: 100, request=self.request)
        self.assertNotIn("PRIVATE", json.dumps(observed))
        self.assertNotIn("size", observed)
        self.assertNotIn("size_vram", observed)

    def test_runtime_transport_error_is_not_retried(self):
        def broken(*args):
            self.calls.append(args)
            raise TimeoutError("PRIVATE")
        with self.assertRaises(TimeoutError):
            runtime.prepare(1000, clock=lambda: 100, request=broken)
        self.assertEqual(len(self.calls), 1)

    def test_workflow_owns_distinct_port_clean_daemon_and_cache_and_retains_budgets(self):
        text = (ROOT / ".github/workflows/general-news-producer.yml").read_text(encoding="utf-8")
        self.assertIn("export OLLAMA_HOST=127.0.0.1:11435", text)
        self.assertIn('export OLLAMA_MODELS="$HOME/.ollama/models"', text)
        self.assertIn('env -i PATH="$PATH" HOME="$HOME"', text)
        self.assertIn('kill -0 "$owned_pid"', text)
        self.assertIn('trap \'kill "$owned_pid" 2>/dev/null || true\' EXIT', text)
        self.assertIn("OLLAMA_NUM_PARALLEL=1", text)
        self.assertIn("OLLAMA_MAX_LOADED_MODELS=1", text)
        self.assertIn("OLLAMA_CONTEXT_LENGTH=32768", text)
        self.assertIn("scripts/owned_general_news_runtime.py", text)
        self.assertIn("timeout --signal=KILL", text)
        self.assertNotIn("http://127.0.0.1:11434", text)


if __name__ == "__main__":
    unittest.main()
