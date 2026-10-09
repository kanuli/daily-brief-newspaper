#!/usr/bin/env python3
"""Only fake loopback responses and synthetic inputs; no model/news/network."""
from __future__ import annotations

import ast
import json
import types
import urllib.error
import urllib.request
import unittest
from unittest.mock import patch

import test_editorial_gate_diagnostics as gate

NAMESPACE = gate.OBS
FUNCTIONS = {"copy_output_schema", "model_prompt", "ollama_json"}
CONSTANTS = {"MODEL_URL", "MODEL_NAME", "CODE_FENCE_RE"}
NAMESPACE["urllib"] = types.SimpleNamespace(request=urllib.request)
nodes = [node for node in gate.TREE.body if (
    isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS
) or (
    isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id in CONSTANTS for target in node.targets)
)]
exec(compile(ast.Module(body=nodes, type_ignores=[]), str(gate.PROPOSAL), "exec"), NAMESPACE)
base_prompt = next(node for node in gate.BASE_TREE.body if isinstance(node, ast.FunctionDef) and node.name == "model_prompt")
exec(compile(ast.Module(body=[base_prompt], type_ignores=[]), str(gate.BASELINE), "exec"), gate.BASE)


def packet_fixture():
    return {
        "candidateId": "fixture-001", "desk": "synthetic", "sourceName": "NON-NEWS FIXTURE",
        "sourcePageTitle": "SYNTHETIC INPUT", "sourceText": "合成測試材料 7",
    }


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps({"model": "qwen2.5:1.5b", "done": True, "response": json.dumps(self.value)}, ensure_ascii=False).encode("utf-8")


class StructuredContractTests(unittest.TestCase):
    def test_schema_binds_exact_identity_complete_copy_and_two_to_five_facts(self):
        schema = NAMESPACE["copy_output_schema"](packet_fixture())
        self.assertEqual(schema["properties"]["candidateId"], {"type": "string", "enum": ["fixture-001"]})
        self.assertEqual(schema["required"], ["candidateId", "facts", "verifiedCopy"])
        self.assertIs(schema["additionalProperties"], False)
        facts = schema["properties"]["facts"]
        self.assertEqual((facts["minItems"], facts["maxItems"]), (2, 5))
        self.assertEqual(facts["items"], {"type": "string", "minLength": 1})
        copy = schema["properties"]["verifiedCopy"]
        self.assertEqual(copy["required"], list(gate.COPY_FIELDS))
        self.assertEqual(set(copy["properties"]), set(gate.COPY_FIELDS))
        self.assertIs(copy["additionalProperties"], False)
        for field in gate.COPY_FIELDS:
            self.assertEqual(copy["properties"][field]["type"], "string")
            self.assertEqual(copy["properties"][field]["minLength"], 1)

    def test_invalid_identity_does_not_get_repaired_or_guessed(self):
        for value in (None, "", 123, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                NAMESPACE["copy_output_schema"]({"candidateId": value})

    def test_original_grounding_instructions_preserved_with_schema_and_exact_id(self):
        packet = packet_fixture()
        original = gate.BASE["model_prompt"](packet)
        prompt = NAMESPACE["model_prompt"](packet)
        self.assertEqual(original.split("只輸出 JSON：", 1)[0], prompt.split("只輸出符合 OUTPUT_SCHEMA", 1)[0])
        schema_text = prompt.split("OUTPUT_SCHEMA:\n", 1)[1].split("\nINPUT:\n", 1)[0]
        self.assertEqual(json.loads(schema_text), NAMESPACE["copy_output_schema"](packet))
        self.assertIn('"fixture-001"', prompt)
        self.assertNotIn('"candidateId":"..."', prompt)
        self.assertIn("兩個換行字元", prompt)

    def test_loopback_request_uses_same_model_limits_and_schema_object(self):
        packet = packet_fixture()
        schema = NAMESPACE["copy_output_schema"](packet)
        _, value = gate.fixture()
        with patch.object(urllib.request, "urlopen", return_value=FakeResponse(value)) as response:
            returned = NAMESPACE["ollama_json"]("NON-NEWS SYNTHETIC TEST", schema=schema)
        self.assertEqual(returned, value)
        response.assert_called_once()
        request = response.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(body["model"], "qwen2.5:1.5b")
        self.assertEqual(body["format"], schema)
        self.assertIs(body["stream"], False)
        self.assertEqual(body["options"], {"temperature": 0.05, "top_p": 0.7, "num_predict": 1700})
        self.assertEqual(response.call_args.kwargs["timeout"], 240)

    def test_ignored_schema_does_not_bypass_existing_identity_gate(self):
        packet, value = gate.fixture()
        value["candidateId"] = "unrelated"
        schema = NAMESPACE["copy_output_schema"](packet)
        with patch.object(urllib.request, "urlopen", return_value=FakeResponse(value)):
            returned = NAMESPACE["ollama_json"]("NON-NEWS SYNTHETIC TEST", schema=schema)
        self.assertEqual(returned["candidateId"], "unrelated")
        self.assertIsNone(NAMESPACE["valid_output"](packet, returned))

    def test_schema_has_no_unverified_regex_or_editorial_acceptance_override(self):
        schema = NAMESPACE["copy_output_schema"](packet_fixture())
        body = schema["properties"]["verifiedCopy"]["properties"]["body"]
        self.assertNotIn("pattern", body)
        self.assertIn("two newline characters", body["description"])
        packet, value = gate.fixture()
        value["verifiedCopy"]["body"] = "合成單段文字" * 40
        self.assertIsNone(NAMESPACE["valid_output"](packet, value))
        value["verifiedCopy"]["body"] += "\n\n" + "合成文字 999"
        self.assertIsNone(NAMESPACE["valid_output"](packet, value))

    def test_unsupported_schema_is_not_retried_with_unconstrained_json(self):
        schema = NAMESPACE["copy_output_schema"](packet_fixture())
        failure = urllib.error.HTTPError("http://127.0.0.1:11434/api/generate", 400, "synthetic unsupported schema", {}, None)
        with patch.object(urllib.request, "urlopen", side_effect=failure) as response:
            with self.assertRaises(urllib.error.HTTPError):
                NAMESPACE["ollama_json"]("NON-NEWS SYNTHETIC TEST", schema=schema)
        response.assert_called_once()


if __name__ == "__main__":
    unittest.main()

