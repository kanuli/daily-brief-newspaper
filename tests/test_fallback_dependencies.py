#!/usr/bin/env python3
"""Offline regression tests; never run source discovery or publication."""
from __future__ import annotations

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
CHECK_PATH = ROOT / "scripts" / "check_general_news_fallback_dependencies.py"
spec = importlib.util.spec_from_file_location("fallback_dependency_check", CHECK_PATH)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ORIGINAL_WORKFLOW_BLOB = "7eb59f8222165ac5f808e208efea68ae53875f49"
ORIGINAL_FALLBACK_BLOB = "461b826b4607acad3ce74b733e296fe5447b3592"
OLD_INSTALL = "python -m pip install --disable-pip-version-check --quiet opencc-python-reimplemented googlenewsdecoder==0.2.1"
NEW_INSTALL = (
    "python -m pip install --disable-pip-version-check --quiet -r scripts/requirements-general-news-fallback.txt\n"
    "          python scripts/check_general_news_fallback_dependencies.py"
)


def git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def fake_modules(*, selector_ok=True):
    attrs = {"data-n-a-sg": "offline-signature", "data-n-a-ts": "123"}

    class Parser:
        def __init__(self, text):
            if text != check.OFFLINE_HTML:
                raise AssertionError("only offline synthetic HTML may be parsed")

        def css_first(self, selector):
            if selector != "c-wiz > div[jscontroller]":
                raise AssertionError("unexpected decoder selector")
            return types.SimpleNamespace(attributes=attrs) if selector_ok else None

    def decode(source_url, interval=None, timeout=15.0):
        raise AssertionError("dependency test must not call network-capable decoder")

    class OpenCC:
        def __init__(self, config):
            if config != "s2hk":
                raise AssertionError("HK conversion must be preserved")

        def convert(self, text):
            return "新聞" if text == "新闻" else text

    return {
        "selectolax.parser": types.SimpleNamespace(HTMLParser=Parser),
        "googlenewsdecoder": types.SimpleNamespace(gnewsdecoder=decode),
        "opencc": types.SimpleNamespace(OpenCC=OpenCC),
    }


class DependencyRegressionTests(unittest.TestCase):
    def run_check(self, versions=None, modules=None):
        versions = check.EXPECTED_VERSIONS if versions is None else versions
        modules = fake_modules() if modules is None else modules
        with patch.object(check.importlib.metadata, "version", side_effect=versions.__getitem__), patch.object(
            check.importlib, "import_module", side_effect=modules.__getitem__
        ):
            return check.check_dependencies()

    def test_exact_compatible_requirements(self):
        lines = (ROOT / "scripts" / "requirements-general-news-fallback.txt").read_text(encoding="utf-8").splitlines()
        self.assertIn("googlenewsdecoder==0.2.1", lines)
        self.assertIn("selectolax==0.4.12", lines)

    def test_workflow_only_changes_install_and_adds_offline_check(self):
        changed = (ROOT / ".github" / "workflows" / "general-news-producer.yml").read_text(encoding="utf-8")
        self.assertEqual(changed.count(NEW_INSTALL), 1)
        # The separately reviewed editorial trial adds immutable ownership and
        # exact persisted-draft proof; the dependency contract stays unchanged.
        baseline = (ROOT / "tests/fixtures/original_general_news_producer.yml").read_text(encoding="utf-8")
        self.assertEqual(baseline.count(NEW_INSTALL), 1)
        original = baseline.replace(NEW_INSTALL, OLD_INSTALL).encode("utf-8")
        self.assertEqual(git_blob_sha(original), ORIGINAL_WORKFLOW_BLOB)
        for constraint in ("--available-tools='view,web_search,web_fetch'", "--available-tools='view'",
                           "scripts/general_news_verification_robot.py merge", "scripts/general_news_verification_robot.py produce"):
            self.assertIn(constraint, baseline)
            self.assertIn(constraint, changed)

    def test_source_and_editorial_gates_are_byte_identical(self):
        baseline_path = ROOT / "tests/fixtures/original_local_fallback_gates.py"
        self.assertEqual(git_blob_sha(baseline_path.read_bytes()), ORIGINAL_FALLBACK_BLOB)
        baseline = baseline_path.read_text(encoding="utf-8")
        current = (ROOT / "scripts/general_news_local_fallback.py").read_text(encoding="utf-8")
        names = {"trusted", "choose", "safe_http_url", "fetch", "bing_search", "decoded_candidate_url",
                 "extract_source_page", "source_packet", "allowed_numbers", "valid_output"}
        def functions(source):
            return {node.name: ast.get_source_segment(source, node)
                    for node in ast.parse(source).body
                    if isinstance(node, ast.FunctionDef) and node.name in names}
        self.assertEqual(set(functions(baseline)), names)
        self.assertEqual(functions(current), functions(baseline))

    def test_supported_api_smoke_is_offline(self):
        self.assertEqual(self.run_check(), check.EXPECTED_VERSIONS)

    def test_selectolax_1_is_rejected_before_import(self):
        versions = {**check.EXPECTED_VERSIONS, "selectolax": "1.0.0"}
        with patch.object(check.importlib.metadata, "version", side_effect=versions.__getitem__), patch.object(
            check.importlib, "import_module"
        ) as imports:
            with self.assertRaisesRegex(RuntimeError, "verified compatibility version"):
                check.check_dependencies()
            imports.assert_not_called()

    def test_selector_api_failure_remains_fail_closed(self):
        with self.assertRaisesRegex(RuntimeError, "contract failed"):
            self.run_check(modules=fake_modules(selector_ok=False))

    def test_missing_decoder_dependency_is_not_success(self):
        def load_module(name):
            if name == "googlenewsdecoder":
                raise ImportError("incompatible transitive parser")
            return fake_modules()[name]

        with patch.object(check.importlib.metadata, "version", side_effect=check.EXPECTED_VERSIONS.__getitem__), patch.object(
            check.importlib, "import_module", side_effect=load_module
        ):
            with self.assertRaises(ImportError):
                check.check_dependencies()

    def test_cli_failure_is_nonzero(self):
        with patch.object(check, "check_dependencies", side_effect=ImportError("decoder unavailable")), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(check.main([]), 1)
        self.assertIn("GENERAL_NEWS_FALLBACK_DEPENDENCIES_FAILED", output.getvalue())

    def test_normal_cli_success_protocol_is_unchanged(self):
        with patch.object(check, "check_dependencies", return_value=check.EXPECTED_VERSIONS), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(check.main([]), 0)
        self.assertEqual(
            output.getvalue(),
            "GENERAL_NEWS_FALLBACK_DEPENDENCIES_OK " + json.dumps(check.EXPECTED_VERSIONS, sort_keys=True) + "\n",
        )

    def test_json_only_success_is_exact_versions_without_banner(self):
        with patch.object(check, "check_dependencies", return_value=check.EXPECTED_VERSIONS), contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(check.main(["--json-only"]), 0)
        self.assertEqual(json.loads(output.getvalue()), check.EXPECTED_VERSIONS)
        self.assertEqual(output.getvalue().count("\n"), 1)
        self.assertEqual(errors.getvalue(), "")

    def test_json_only_failure_is_nonzero_and_has_no_success_stdout(self):
        with patch.object(check, "check_dependencies", side_effect=ImportError("secret-token-detail")), contextlib.redirect_stdout(io.StringIO()) as output, contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(check.main(["--json-only"]), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(json.loads(errors.getvalue()), {"error": "ImportError"})
        self.assertNotIn("secret-token-detail", errors.getvalue())


if __name__ == "__main__":
    unittest.main()

