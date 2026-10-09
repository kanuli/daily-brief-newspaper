#!/usr/bin/env python3
"""Synthetic source workers and model responses only; no network or news writes."""
from __future__ import annotations

import ast
import contextlib
import io
import json
import math
import os
from pathlib import Path
import runpy
import subprocess
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "scripts/general_news_local_fallback.py"
BASELINE = ROOT / "tests/fixtures/original_local_fallback_gates.py"
SOURCE = PROPOSAL.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)
BASE_SOURCE = BASELINE.read_text(encoding="utf-8")
BASE_TREE = ast.parse(BASE_SOURCE)


def load_synthetic_module():
    nodes = []
    for node in TREE.body:
        if isinstance(node, ast.ImportFrom) and node.module in {"opencc", "googlenewsdecoder"}:
            continue
        if isinstance(node, ast.Import) and any(alias.name == "general_news_verified_producer" for alias in node.names):
            continue
        if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "HK" for target in node.targets):
            continue
        nodes.append(node)
    module = types.ModuleType("synthetic_source_budget_fallback")
    module.__file__ = str(PROPOSAL)
    module.HK = types.SimpleNamespace(convert=lambda text: text)
    module.producer = types.SimpleNamespace(**runpy.run_path(str(ROOT / "scripts/general_news_verified_producer.py")))
    module.gnewsdecoder = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no network"))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(PROPOSAL), "exec"), module.__dict__)
    return module


def candidate(desk, rank=0, *, cid=None, source="Reuters"):
    return {
        "id": cid or f"{desk}-{rank}", "desk": desk,
        "title": f"SYNTHETIC material event {desk} {rank} - TEST MEDIA",
        "source": source, "url": f"https://example.com/{desk}/{rank}",
        "publishedAt": f"2026-10-09T{20-rank:02d}:00:00Z",
    }


def request(desks=None, ranks=4):
    desks = desks or ["world", "asia", "hong-kong", "japan", "finance", "ai-tech", "manga-anime", "other-desk-1", "other-desk-2"]
    return {"staleDesks": desks, "candidates": [candidate(desk, rank) for desk in desks for rank in range(ranks)]}


def packet(row):
    return {
        "candidateId": row["id"], "desk": row["desk"],
        "originalTitle": row["title"].rsplit(" - ", 1)[0],
        "sourceName": row["source"], "directUrl": row["url"],
        "sourcePageTitle": "SYNTHETIC fixture", "sourceText": "合成材料" * 100,
    }


def structured_copy(source_packet):
    return {
        "candidateId": source_packet["candidateId"],
        "facts": ["合成測試事實甲", "合成測試事實乙"],
        "verifiedCopy": {
            field: (["合成第一段" * 30, "合成第二段" * 30] if field == "body" else "合成測試文字" * 10)
            for field in ("title", "dek", "summary", "body", "context", "why", "watchNext")
        },
    }


class Clock:
    def __init__(self):
        self.mono = 50.0
        self.wall = 1000.0


class SourceSelectionBudgetTests(unittest.TestCase):
    def setUp(self):
        self.module = load_synthetic_module()
        self.clock = Clock()

    def response(self, value, returncode=0):
        return types.SimpleNamespace(returncode=returncode, stdout=json.dumps(value, ensure_ascii=False), stderr="PRIVATE-WORKER-ERROR")

    def run_main(self, data, source_behavior, model_behavior=None, *, deadline=None, daily_ready=False):
        calls, models, writes = [], [], []

        def source_run(command, **kwargs):
            row = json.loads(kwargs["input"])
            calls.append((row, command, kwargs))
            return source_behavior(row, kwargs)

        def model(prompt, **kwargs):
            models.append((prompt, kwargs))
            source_packet = json.JSONDecoder().raw_decode(prompt.split("INPUT:\n", 1)[1])[0]
            return model_behavior(source_packet, kwargs) if model_behavior else structured_copy(source_packet)

        args = ["fallback", "SYNTHETIC_REQUEST", "--facts", "NEVER_WRITTEN_FACTS", "--copies", "NEVER_WRITTEN_COPIES"]
        if deadline is not None:
            args += ["--deadline-unix=" + deadline]
        if daily_ready:
            args += ["--daily-ready-copy"]
        error = None
        with patch.object(sys, "argv", args), patch.object(self.module, "load", return_value=data), \
                patch.object(self.module.subprocess, "run", side_effect=source_run), \
                patch.object(self.module, "ollama_json", side_effect=model), \
                patch.object(self.module.time, "monotonic", side_effect=lambda: self.clock.mono), \
                patch.object(self.module.time, "time", side_effect=lambda: self.clock.wall), \
                patch.object(Path, "write_text", side_effect=lambda content, **kwargs: writes.append(content)), \
                contextlib.redirect_stdout(io.StringIO()) as output:
            try:
                result = self.module.main()
            except SystemExit as exc:
                error, result = str(exc), None
        diagnostic_lines = [line for line in output.getvalue().splitlines() if line.startswith("LOCAL_FALLBACK_DIAGNOSTIC ")]
        diagnostics = json.loads(diagnostic_lines[0].removeprefix("LOCAL_FALLBACK_DIAGNOSTIC ")) if diagnostic_lines else []
        return types.SimpleNamespace(calls=calls, models=models, writes=writes, error=error, result=result, diagnostics=diagnostics, output=output.getvalue())

    def good_source(self, row, kwargs):
        return self.response({"packet": packet(row), "diagnostic": None})

    def no_source(self, row, kwargs):
        return self.response({"packet": None, "diagnostic": "no-direct-source-text"})

    def test_original_source_and_editorial_functions_are_byte_identical(self):
        preserved = {"choose", "trusted", "source_packet", "extract_source_page", "fetch", "safe_http_url", "decoded_candidate_url", "bing_search", "valid_output", "allowed_numbers"}
        for name in preserved:
            with self.subTest(function=name):
                old = next(node for node in BASE_TREE.body if isinstance(node, ast.FunctionDef) and node.name == name)
                new = next(node for node in TREE.body if isinstance(node, ast.FunctionDef) and node.name == name)
                self.assertEqual(ast.get_source_segment(BASE_SOURCE, old), ast.get_source_segment(SOURCE, new))

    def test_round_robin_reaches_second_hong_kong_at_attempt_twelve(self):
        data = request()
        queue = self.module.bounded_source_queue(data)
        self.assertEqual(len(queue), 36)
        self.assertEqual([row["desk"] for row in queue[:9]], data["staleDesks"])
        self.assertEqual(queue[11]["id"], "hong-kong-1")
        self.assertEqual(len(self.module.choose(data)), 3)
        result = self.run_main(data, lambda row, kwargs: self.good_source(row, kwargs) if row["id"] == "hong-kong-1" else self.no_source(row, kwargs))
        self.assertIsNone(result.error)
        self.assertEqual(len(result.calls), 12)
        self.assertEqual(len(result.models), 1)
        self.assertEqual([item["candidateId"] for item in json.loads(result.writes[1])["articles"]], ["hong-kong-1"])

    def test_ranking_primary_then_newest_is_unchanged_and_four_per_desk(self):
        data = request(["hong-kong"], ranks=6)
        data["candidates"][5]["source"] = "香港政府新聞網"
        queue = self.module.bounded_source_queue(data)
        self.assertEqual([row["id"] for row in queue], ["hong-kong-5", "hong-kong-0", "hong-kong-1", "hong-kong-2"])
        self.assertEqual(self.module.choose(data)[0], queue[0])

    def test_global_ids_duplicate_desks_unknown_desks_and_untrusted_rows_are_not_retried(self):
        data = request(["world", "asia", "world"], ranks=2)
        data["candidates"] += [candidate("asia", cid="world-0"), candidate("world", cid="untrusted", source="UNKNOWN NONTRUSTED"), candidate("not-stale"), candidate("world", cid="")]
        data["candidates"][-1]["id"] = ""
        queue = self.module.bounded_source_queue(data)
        ids = [row["id"] for row in queue]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {"world-0", "world-1", "asia-0", "asia-1"})

    def test_twelve_failed_source_attempts_make_zero_model_calls_and_no_files(self):
        result = self.run_main(request(), self.no_source)
        self.assertEqual(len(result.calls), 12)
        self.assertEqual(result.models, [])
        self.assertEqual(result.writes, [])
        self.assertEqual(result.error, "LOCAL_FALLBACK_NO_VERIFIED_SOURCE_PAGE_COPY")

    def test_three_failed_model_calls_are_counted_before_invocation(self):
        def failure(packet, kwargs):
            raise RuntimeError("PRIVATE-MODEL-TOKEN")
        result = self.run_main(request(), self.good_source, failure)
        self.assertEqual(len(result.calls), 3)
        self.assertEqual(len(result.models), 3)
        self.assertEqual(result.writes, [])
        self.assertNotIn("PRIVATE-MODEL-TOKEN", result.output)

    def test_three_editorial_rejections_cannot_increase_model_budget(self):
        def wrong_identity(packet, kwargs):
            copy_value = structured_copy(packet)
            copy_value["candidateId"] = "unrelated"
            return copy_value
        result = self.run_main(request(), self.good_source, wrong_identity)
        self.assertEqual(len(result.models), 3)
        self.assertEqual(result.writes, [])
        self.assertTrue(all("candidate-id-mismatch" in item["reasonCodes"] for item in result.diagnostics))

    def test_accepted_desk_is_skipped_even_with_later_source_alternatives(self):
        data = request(["hong-kong", "asia"], ranks=4)
        result = self.run_main(data, lambda row, kwargs: self.good_source(row, kwargs) if row["desk"] == "hong-kong" else self.no_source(row, kwargs))
        self.assertEqual([row["id"] for row, _, _ in result.calls], ["hong-kong-0", "asia-0", "asia-1", "asia-2", "asia-3"])
        self.assertEqual(len(result.models), 1)
        self.assertEqual(len(json.loads(result.writes[1])["articles"]), 1)

    def test_worker_uses_fixed_argv_stdin_no_shell_and_stripped_credentials(self):
        inherited = {"PATH": "SAFE-PATH", "LANG": "C.UTF-8", "GH_TOKEN": "PRIVATE-TOKEN", "GITHUB_TOKEN": "PRIVATE-TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "PRIVATE-TOKEN", "AWS_SECRET_ACCESS_KEY": "PRIVATE-TOKEN", "HTTPS_PROXY": "https://secret@example.com", "PYTHONPATH": "PRIVATE-PATH"}
        with patch.dict(os.environ, inherited, clear=True):
            result = self.run_main(request(["hong-kong"], ranks=1), self.good_source)
        row, command, kwargs = result.calls[0]
        self.assertEqual(command, [sys.executable, "-X", "utf8", str(PROPOSAL.resolve()), "--source-worker"])
        self.assertFalse(kwargs["shell"])
        self.assertFalse(kwargs["check"])
        self.assertTrue(kwargs["capture_output"])
        self.assertEqual(kwargs["timeout"], 35)
        self.assertEqual(json.loads(kwargs["input"]), row)
        self.assertEqual(kwargs["env"], {"PATH": "SAFE-PATH", "LANG": "C.UTF-8", "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"})
        self.assertNotIn("PRIVATE-TOKEN", result.output)

    def test_timeout_and_worker_exception_diagnostics_do_not_leak_internal_output(self):
        for exception, code in ((subprocess.TimeoutExpired("private-command", 1, output="PRIVATE-SOURCE", stderr="PRIVATE-TOKEN"), "source-timeout"), (OSError("PRIVATE-TOKEN"), "source-worker-failed")):
            with self.subTest(code=code):
                def failure(row, kwargs):
                    raise exception
                result = self.run_main(request(["hong-kong"], ranks=1), failure)
                self.assertEqual(result.diagnostics[0]["reasonCode"], code)
                self.assertNotIn("PRIVATE", result.output)
                self.assertEqual(result.models, [])

    def test_worker_protocol_is_exact_not_best_effort_parsing(self):
        row = candidate("hong-kong")
        invalid_packets = []
        for field, value in (("candidateId", "other"), ("desk", "other"), ("sourceName", "other"), ("originalTitle", "other"), ("sourceText", "short"), ("sourceText", "x" * 9001), ("directUrl", "file:///private"), ("directUrl", "https://secret:token@example.com"), ("directUrl", "http://localhost/story"), ("directUrl", "http://127.0.0.1/story"), ("directUrl", "http://10.0.0.1/story"), ("directUrl", "http://[::1]/story"), ("directUrl", "https://nas.local/story")):
            altered = packet(row)
            altered[field] = value
            invalid_packets.append({"packet": altered, "diagnostic": None})
        invalid_packets += [{"packet": packet(row), "diagnostic": None, "extra": "PRIVATE"}, {"packet": None, "diagnostic": "PRIVATE-TOKEN"}, {"packet": packet(row), "diagnostic": "source-worker-failed"}]
        for invalid in invalid_packets:
            with self.subTest(invalid=invalid):
                result = self.run_main(request(["hong-kong"], ranks=1), lambda row, kwargs: self.response(invalid))
                self.assertEqual(result.diagnostics[0]["reasonCode"], "source-worker-protocol-invalid")
                self.assertEqual(result.models, [])
                self.assertEqual(result.writes, [])
                self.assertNotIn("PRIVATE", result.output)
        nonzero = self.run_main(request(["hong-kong"], ranks=1), lambda row, kwargs: self.response({"packet": packet(row), "diagnostic": None}, returncode=1))
        self.assertEqual(nonzero.diagnostics[0]["reasonCode"], "source-worker-failed")

    def test_malformed_or_expired_deadlines_fail_before_source_work(self):
        for deadline in ("", "not-a-number", "nan", "inf", "-inf", "1000", "999"):
            with self.subTest(deadline=deadline):
                result = self.run_main(request(), self.good_source, deadline=deadline)
                self.assertEqual(result.error, "LOCAL_FALLBACK_DEADLINE_INVALID_OR_EXPIRED")
                self.assertEqual((result.calls, result.models, result.writes), ([], [], []))

    def test_external_deadline_clamps_source_and_model_timeouts(self):
        result = self.run_main(request(["hong-kong"], ranks=1), self.good_source, deadline="1020")
        self.assertEqual(result.calls[0][2]["timeout"], 20)
        self.assertEqual(result.models[0][1]["timeout"], 20)
        distant = self.run_main(request(["hong-kong"], ranks=1), self.good_source, deadline="10000")
        self.assertEqual(distant.calls[0][2]["timeout"], 35)
        self.assertEqual(distant.models[0][1]["timeout"], 240)

    def test_wall_clock_change_cannot_extend_monotonic_deadline(self):
        with patch.object(self.module.time, "monotonic", side_effect=lambda: self.clock.mono), patch.object(self.module.time, "time", side_effect=lambda: self.clock.wall):
            deadline = self.module.monotonic_run_deadline("1100")
            self.clock.mono += 30
            self.clock.wall -= 10000
            self.assertEqual(self.module.remaining_seconds(deadline), 70)
            self.clock.mono += 71
            self.assertEqual(self.module.remaining_seconds(deadline), 0)

    def test_source_completion_after_deadline_never_calls_model(self):
        def late_source(row, kwargs):
            self.clock.mono += 21
            return self.good_source(row, kwargs)
        result = self.run_main(request(), late_source, deadline="1020")
        self.assertEqual(len(result.calls), 1)
        self.assertEqual(result.models, [])
        self.assertEqual(result.writes, [])
        self.assertEqual(result.diagnostics[0]["reasonCode"], "source-deadline-expired")

    def test_late_model_response_cannot_write_or_trigger_another_call(self):
        def late_model(packet, kwargs):
            self.clock.mono += 21
            return structured_copy(packet)
        result = self.run_main(request(), self.good_source, late_model, deadline="1020")
        self.assertEqual((len(result.calls), len(result.models)), (1, 1))
        self.assertEqual(result.writes, [])
        self.assertEqual(result.diagnostics[0]["error"], "run-deadline-expired")

    def test_prompt_preparation_cannot_start_model_after_deadline(self):
        original_prompt = self.module.model_prompt
        def late_prompt(source_packet):
            self.clock.mono += 21
            return original_prompt(source_packet)
        with patch.object(self.module, "model_prompt", side_effect=late_prompt):
            result = self.run_main(request(), self.good_source, deadline="1020")
        self.assertEqual(len(result.calls), 1)
        self.assertEqual(result.models, [])
        self.assertEqual(result.writes, [])
        self.assertEqual(result.diagnostics[0]["error"], "run-deadline-expired")

    def test_default_budget_is_six_hundred_seconds_and_cannot_grow(self):
        with patch.object(self.module.time, "monotonic", return_value=10), patch.object(self.module.time, "time", return_value=1000):
            self.assertEqual(self.module.monotonic_run_deadline(None), 610)
            self.assertEqual(self.module.monotonic_run_deadline("9999999999"), 610)

    def test_model_dynamic_timeout_validates_bounds_and_retains_default(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
            def read(self):
                return json.dumps({"model": "gemma3:4b-it-qat", "done": True, "response": "{}"}).encode()
        for timeout in (0, -1, math.inf, math.nan, 241):
            with self.subTest(timeout=timeout), patch.object(self.module.urllib.request, "urlopen") as http:
                with self.assertRaises(ValueError):
                    self.module.ollama_json("SYNTHETIC", schema={}, timeout=timeout)
                http.assert_not_called()
        for supplied, expected in (({}, 240), ({"timeout": 17.5}, 17.5)):
            with patch.object(self.module.urllib.request, "urlopen", return_value=FakeResponse()) as http:
                self.assertEqual(self.module.ollama_json("SYNTHETIC", schema={}, **supplied), {})
                self.assertEqual(http.call_args.kwargs["timeout"], expected)

    def test_worker_suppresses_library_logs_and_returns_only_strict_ipc(self):
        row = candidate("hong-kong")
        def noisy_source(candidate):
            print("PRIVATE-SOURCE-LIBRARY-OUTPUT")
            print("PRIVATE-TOKEN", file=sys.stderr)
            return packet(candidate)
        with patch.object(sys, "stdin", io.StringIO(json.dumps(row))), patch.object(self.module, "source_packet", side_effect=noisy_source), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(self.module.source_worker_main(), 0)
        returned = json.loads(output.getvalue())
        self.assertEqual(returned, {"packet": packet(row), "diagnostic": None})
        self.assertNotIn("PRIVATE", output.getvalue())

    def test_worker_locator_error_has_fixed_reason_without_exception_body(self):
        with patch.object(sys, "stdin", io.StringIO(json.dumps(candidate("hong-kong")))), patch.object(self.module, "source_packet", side_effect=self.module.ET.ParseError("PRIVATE-SOURCE")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.module.source_worker_main()
        self.assertEqual(json.loads(output.getvalue()), {"packet": None, "diagnostic": "locator-rss-invalid-xml"})
        self.assertNotIn("PRIVATE", output.getvalue())

    def test_worker_rejects_oversized_invalid_or_untrusted_input_before_fetch(self):
        untrusted = candidate("hong-kong", source="UNKNOWN NONTRUSTED")
        missing_id = candidate("hong-kong")
        missing_id["id"] = ""
        for raw in ("PRIVATE" * 10_000, "not-json", "[]", json.dumps(untrusted), json.dumps(missing_id)):
            with self.subTest(raw=raw[:30]), patch.object(sys, "stdin", io.StringIO(raw)), patch.object(self.module, "source_packet") as source, contextlib.redirect_stdout(io.StringIO()) as output:
                self.module.source_worker_main()
                source.assert_not_called()
                self.assertEqual(json.loads(output.getvalue()), {"packet": None, "diagnostic": "source-worker-failed"})
                self.assertNotIn("PRIVATE", output.getvalue())


if __name__ == "__main__":
    unittest.main()
