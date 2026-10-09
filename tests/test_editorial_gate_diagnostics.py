#!/usr/bin/env python3
"""AST-loaded synthetic tests: no packages, source fetch, model or news writes."""
from __future__ import annotations

import ast
import contextlib
import copy
import html
import io
import json
from pathlib import Path
import re
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
PROPOSAL = ROOT / "scripts/general_news_local_fallback.py"
BASELINE = ROOT / "tests/fixtures/original_local_fallback_gates.py"
COPY_FIELDS = ("title", "dek", "summary", "body", "context", "why", "watchNext")


def load_functions(path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    wanted_functions = {"clean", "allowed_numbers", "valid_output", "editorial_gate_diagnostics", "copy_output_schema", "canonical_copy_output", "main"}
    wanted_constants = {"NUM_RE", "CJK_RE", "KANA_RE", "BANNED_PUBLIC"}
    nodes = [node for node in tree.body if (
        isinstance(node, ast.FunctionDef) and node.name in wanted_functions
    ) or (
        isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in wanted_constants for target in node.targets)
    )]
    namespace = {
        "re": re, "html": html, "Any": object, "Path": Path, "ET": ET, "json": json,
        "HK": types.SimpleNamespace(convert=lambda text: text),
        "producer": types.SimpleNamespace(
            COPY_FIELDS=COPY_FIELDS,
            PROCESS_FILLER=re.compile(r"只整理來源標題|標題以外.*公開來源支持|讀者可經原文連結|事件仍可能隨官方聲明|資訊邊界維持|只採用來源標題|補回相應新聞頁"),
            TITLE_SUFFIX=re.compile(r" - TEST MEDIA$"),
        ),
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), namespace)
    return source, tree, namespace


BASE_SOURCE, BASE_TREE, BASE = load_functions(BASELINE)
SOURCE, TREE, OBS = load_functions(PROPOSAL)


def fixture():
    packet = {"candidateId": "fixture-001", "sourceText": "synthetic source 7", "sourcePageTitle": "fixture"}
    value = {
        "candidateId": "fixture-001", "facts": ["合成事實甲", "合成事實乙"],
        "verifiedCopy": {field: "合成文字" * 10 for field in COPY_FIELDS},
    }
    value["verifiedCopy"]["body"] = "合成測試文字" * 15 + "\n\n" + "合成測試文字" * 15
    return packet, value


class EditorialDiagnosticsTests(unittest.TestCase):
    def test_canonical_source_and_probe_revision_are_not_changed_by_proposal(self):
        self.assertNotEqual(PROPOSAL, BASELINE)
        # The reviewed runtime remains in its original fixture; this observer
        # must never itself be used to claim a new infrastructure capability.
        reviewed = (ROOT / "scripts/probe_general_news_fallback_capability.py").read_text(encoding="utf-8")
        self.assertIn("eb3707b28647cbb1a78a306446df9f4c7422f951dd1b63fbd851e5d9289c9a1e", reviewed)

    def test_editorial_acceptance_function_is_byte_identical_normalized_text(self):
        def segment(source, tree):
            node = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "valid_output")
            return ast.get_source_segment(source, node)
        self.assertEqual(segment(BASE_SOURCE, BASE_TREE), segment(SOURCE, TREE))

    def test_valid_fixture_keeps_identical_acceptance(self):
        packet, value = fixture()
        self.assertIsNotNone(BASE["valid_output"](packet, value))
        self.assertEqual(BASE["valid_output"](packet, value), OBS["valid_output"](packet, value))

    def assert_rejection(self, mutator, expected_code):
        packet, value = fixture()
        mutator(packet, value)
        self.assertIsNone(BASE["valid_output"](packet, value))
        self.assertEqual(BASE["valid_output"](packet, value), OBS["valid_output"](packet, value))
        diagnostic = OBS["editorial_gate_diagnostics"](packet, value)
        self.assertIn(expected_code, diagnostic["reasonCodes"])
        return diagnostic

    def test_each_existing_rejection_has_a_fixed_reason_code(self):
        cases = (
            (lambda p, v: v.update(candidateId="other"), "candidate-id-mismatch"),
            (lambda p, v: v.update(facts=["合成一項事實"]), "insufficient-facts"),
            (lambda p, v: v.update(verifiedCopy=[]), "copy-object-missing"),
            (lambda p, v: v["verifiedCopy"].update(summary=""), "missing-copy-fields"),
            (lambda p, v: v["verifiedCopy"].update(summary="合成數字 9999"), "ungrounded-numeric-token"),
            (lambda p, v: v["verifiedCopy"].update(summary="只整理來源標題"), "process-language"),
            (lambda p, v: v["verifiedCopy"].update(summary="RSS"), "banned-public-language"),
            (lambda p, v: v["verifiedCopy"].update(body="合成測試文字" * 40), "body-paragraph-break-missing"),
            (lambda p, v: v.update(verifiedCopy={field: "短\n\n文" for field in COPY_FIELDS}), "copy-too-short"),
            (lambda p, v: v["verifiedCopy"].update(summary="ア" * 9), "excessive-japanese-kana"),
        )
        for mutate, code in cases:
            with self.subTest(code=code):
                self.assert_rejection(mutate, code)

    def test_counts_and_field_names_do_not_leak_copy_source_or_numbers(self):
        packet, value = fixture()
        packet["sourceText"] += " SOURCE-SECRET-TEXT"
        value["verifiedCopy"]["body"] += " ARTICLE-SECRET-TEXT 987654321"
        diagnostic = OBS["editorial_gate_diagnostics"](packet, value)
        output = json.dumps(diagnostic, ensure_ascii=False)
        self.assertNotIn("SOURCE-SECRET-TEXT", output)
        self.assertNotIn("ARTICLE-SECRET-TEXT", output)
        self.assertNotIn("987654321", output)
        self.assertEqual(diagnostic["ungroundedNumericTokenCount"], 1)
        self.assertEqual(set(diagnostic["copyFieldCharacters"]), set(COPY_FIELDS))
        self.assertTrue(all(type(size) is int for size in diagnostic["copyFieldCharacters"].values()))

    def run_rejected_main(self, *, source_error=None, diagnostic_error=False, malformed_body=False):
        packet, value = fixture()
        value["candidateId"] = "bad-identity"
        if not malformed_body:
            value["verifiedCopy"]["body"] = ["合成第一段" * 15, "合成第二段" * 15]
        namespace = dict(OBS)
        # Main's function globals are the namespace originally compiled above.
        original = dict(OBS)
        import argparse
        OBS.update({
            "argparse": argparse, "load": lambda path: {},
            "choose": lambda request: [{"id": "fixture-001"}],
            "source_packet": lambda candidate: packet,
            "model_prompt": lambda packet: "NON-NEWS SYNTHETIC TEST",
            "ollama_json": lambda prompt, **kwargs: value,
        })
        if source_error:
            def fail_source(candidate):
                raise source_error
            OBS["source_packet"] = fail_source
        if diagnostic_error:
            def fail_diagnostic(*args):
                raise RuntimeError("secret-error-text")
            OBS["editorial_gate_diagnostics"] = fail_diagnostic
        argv = ["fallback", "synthetic-request", "--facts", "never-written-facts", "--copies", "never-written-copy"]
        try:
            with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()) as output:
                with self.assertRaisesRegex(SystemExit, "LOCAL_FALLBACK_NO_VERIFIED_SOURCE_PAGE_COPY"):
                    OBS["main"]()
            line = output.getvalue().strip()
            self.assertTrue(line.startswith("LOCAL_FALLBACK_DIAGNOSTIC "))
            return json.loads(line.removeprefix("LOCAL_FALLBACK_DIAGNOSTIC "))
        finally:
            OBS.clear()
            OBS.update(original)

    def test_rejection_observer_does_not_create_facts_or_copy_files(self):
        with patch.object(Path, "write_text", side_effect=AssertionError("no news writes")):
            diagnostic = self.run_rejected_main()
        self.assertEqual(diagnostic[0]["reasonCodes"], ["candidate-id-mismatch"])

    def test_observation_exception_preserves_original_rejection_without_leaking(self):
        with patch.object(Path, "write_text", side_effect=AssertionError("no news writes")):
            diagnostic = self.run_rejected_main(diagnostic_error=True)
        self.assertEqual(diagnostic[0]["reasonCodes"], ["diagnostic-unavailable"])
        self.assertEqual(diagnostic[0]["diagnosticError"], "RuntimeError")
        self.assertNotIn("secret-error-text", json.dumps(diagnostic))

    def test_invalid_model_paragraph_representation_never_guesses_breaks_or_writes_copy(self):
        with patch.object(Path, "write_text", side_effect=AssertionError("no news writes")):
            diagnostic = self.run_rejected_main(malformed_body=True)
        self.assertEqual(diagnostic[0]["stage"], "model-format")
        self.assertEqual(diagnostic[0]["reasonCodes"], ["body-paragraph-representation-invalid"])
        self.assertNotIn("合成測試文字", json.dumps(diagnostic, ensure_ascii=False))

    def test_rss_parse_error_identifies_locator_not_article_html_parser(self):
        diagnostic = self.run_rejected_main(source_error=ET.ParseError("secret-response-body"))
        self.assertEqual(diagnostic[0]["reasonCode"], "locator-rss-invalid-xml")
        self.assertEqual(diagnostic[0]["error"], "ParseError")
        self.assertNotIn("secret-response-body", json.dumps(diagnostic))
        self.assertEqual(SOURCE.count("ET.fromstring("), 1)


if __name__ == "__main__":
    unittest.main()


