#!/usr/bin/env python3
"""Only fake loopback responses and synthetic inputs; no model/news/network."""
from __future__ import annotations

import ast
import copy
import json
import math
import types
import urllib.error
import urllib.request
import unittest
from unittest.mock import patch

import test_editorial_gate_diagnostics as gate

NAMESPACE = gate.OBS
FUNCTIONS = {"copy_output_schema", "canonical_copy_output", "model_prompt", "ollama_json", "model_runtime_metadata"}
CONSTANTS = {"MODEL_URL", "MODEL_NAME", "CODE_FENCE_RE", "MODEL_CONTEXT", "TARGET_COPY_PATTERN", "MODEL_SYSTEM"}
NAMESPACE["urllib"] = types.SimpleNamespace(request=urllib.request)
NAMESPACE["math"] = math
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


def structured_fixture(paragraph_count=2):
    packet, value = gate.fixture()
    value["verifiedCopy"]["body"] = [
        "合成第一段材料" * 15, "合成第二段材料" * 15, "合成第三段材料" * 15,
    ][:paragraph_count]
    return packet, value


class FakeResponse:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self):
        return json.dumps({"model": "gemma3:4b-it-qat", "done": True, "response": json.dumps(self.value)}, ensure_ascii=False).encode("utf-8")


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
            if field == "body":
                body = copy["properties"][field]
                self.assertEqual(body["type"], "array")
                self.assertEqual(body["items"], {"type": "string", "minLength": 1, "pattern": NAMESPACE["TARGET_COPY_PATTERN"]})
                self.assertEqual((body["minItems"], body["maxItems"]), (2, 3))
            else:
                self.assertEqual(copy["properties"][field]["type"], "string")
                self.assertEqual(copy["properties"][field]["minLength"], 1)
                self.assertEqual(copy["properties"][field]["pattern"], NAMESPACE["TARGET_COPY_PATTERN"])

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
        self.assertIn("非空段落字串的陣列", prompt)
        self.assertIn("不同的新聞事實或解說重點", prompt)
        self.assertIn("全部由 SOURCE_TEXT 直接支持", prompt)
        self.assertIn("不得重複、填充、拆句湊段或新增材料", prompt)

    def test_loopback_request_uses_same_model_limits_and_schema_object(self):
        packet = packet_fixture()
        schema = NAMESPACE["copy_output_schema"](packet)
        _, value = structured_fixture()
        with patch.object(urllib.request, "urlopen", return_value=FakeResponse(value)) as response:
            returned = NAMESPACE["ollama_json"]("NON-NEWS SYNTHETIC TEST", schema=schema)
        self.assertEqual(returned, value)
        response.assert_called_once()
        request = response.call_args.args[0]
        body = json.loads(request.data)
        self.assertEqual(request.full_url, "http://127.0.0.1:11434/api/generate")
        self.assertEqual(body["model"], "gemma3:4b-it-qat")
        self.assertEqual(body["format"], schema)
        self.assertIs(body["stream"], False)
        self.assertIs(body["truncate"], False)
        self.assertIs(body["shift"], False)
        self.assertNotIn("system", body)
        self.assertEqual(body["prompt"], NAMESPACE["MODEL_SYSTEM"] + "\n\nNON-NEWS SYNTHETIC TEST")
        self.assertEqual(body["options"], {"temperature": 0.05, "top_p": 0.7, "num_predict": 1700, "num_ctx": 32768})
        self.assertEqual(response.call_args.kwargs["timeout"], 240)

    def test_ignored_schema_does_not_bypass_existing_identity_gate(self):
        packet, value = structured_fixture()
        value["candidateId"] = "unrelated"
        schema = NAMESPACE["copy_output_schema"](packet)
        with patch.object(urllib.request, "urlopen", return_value=FakeResponse(value)):
            returned = NAMESPACE["ollama_json"]("NON-NEWS SYNTHETIC TEST", schema=schema)
        self.assertEqual(returned["candidateId"], "unrelated")
        self.assertIsNone(NAMESPACE["valid_output"](packet, NAMESPACE["canonical_copy_output"](returned)))

    def test_schema_literal_range_has_no_lookaround_or_editorial_acceptance_override(self):
        schema = NAMESPACE["copy_output_schema"](packet_fixture())
        body = schema["properties"]["verifiedCopy"]["properties"]["body"]
        self.assertNotIn("pattern", body)
        self.assertEqual(body["items"]["pattern"], r'^[㐀-鿿][^"\\\u0000-\u001f]*$')
        self.assertNotIn("(?", body["items"]["pattern"])
        self.assertIn("distinct source-grounded", body["description"])
        packet, value = gate.fixture()
        value["verifiedCopy"]["body"] = "合成單段文字" * 40
        self.assertIsNone(NAMESPACE["valid_output"](packet, value))
        value["verifiedCopy"]["body"] += "\n\n" + "合成文字 999"
        self.assertIsNone(NAMESPACE["valid_output"](packet, value))

    def test_serializer_preserves_supplied_paragraphs_and_other_material_without_mutation(self):
        for count in (2, 3):
            with self.subTest(paragraphs=count):
                _, value = structured_fixture(count)
                value["verifiedCopy"]["body"][0] += "  "
                original = copy.deepcopy(value)
                canonical = NAMESPACE["canonical_copy_output"](value)
                expected = copy.deepcopy(original)
                expected["verifiedCopy"]["body"] = "\n\n".join(paragraph.strip() for paragraph in original["verifiedCopy"]["body"])
                self.assertEqual(canonical, expected)
                self.assertEqual(value, original)
                self.assertIsNot(canonical, value)
                self.assertIsNot(canonical["verifiedCopy"], value["verifiedCopy"])
                self.assertEqual(canonical["verifiedCopy"]["body"].count("\n\n"), count - 1)

    def test_serializer_rejects_bad_types_lengths_empty_nonstring_and_embedded_breaks(self):
        invalid = (
            None, "單段字串", "一段\n\n另一段", {}, (), [], ["一段"],
            ["甲", "乙", "丙", "丁"], ["甲", ""], ["甲", " \t "],
            ["甲", None], ["甲", 2], ["甲", False], ["甲", ["乙"]],
            ["甲", {"段": "乙"}], ["甲", "乙\n丙"], ["甲", "乙\r丙"],
        )
        for body in invalid:
            with self.subTest(body=body):
                _, value = structured_fixture()
                value["verifiedCopy"]["body"] = body
                original = copy.deepcopy(value)
                with self.assertRaises(ValueError):
                    NAMESPACE["canonical_copy_output"](value)
                self.assertEqual(value, original)

    def test_serializer_rejects_duplicate_paragraphs_instead_of_padding_copy(self):
        for paragraphs in (["合成段落", "合成段落"], ["合成 段落", "合成  段落"]):
            with self.subTest(paragraphs=paragraphs):
                _, value = structured_fixture()
                value["verifiedCopy"]["body"] = paragraphs
                with self.assertRaises(ValueError):
                    NAMESPACE["canonical_copy_output"](value)

    def test_serializer_rejects_missing_copy_object_or_body(self):
        for value in (None, [], {}, {"verifiedCopy": []}, {"verifiedCopy": {}}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                NAMESPACE["canonical_copy_output"](value)

    def test_serialized_fixture_passes_only_the_unchanged_editorial_gate(self):
        for count in (2, 3):
            with self.subTest(paragraphs=count):
                packet, value = structured_fixture(count)
                canonical = NAMESPACE["canonical_copy_output"](value)
                original_verdict = gate.BASE["valid_output"](packet, canonical)
                self.assertIsNotNone(original_verdict)
                self.assertEqual(NAMESPACE["valid_output"](packet, canonical), original_verdict)

    def test_serialization_never_bypasses_numeric_process_short_or_identity_gates(self):
        cases = (
            ("numeric", lambda v: v["verifiedCopy"].update(summary="合成數字 9999")),
            ("process", lambda v: v["verifiedCopy"].update(summary="只整理來源標題")),
            ("identity", lambda v: v.update(candidateId="unrelated")),
            ("missing-copy", lambda v: v["verifiedCopy"].update(summary="")),
            ("short", lambda v: v.update(verifiedCopy={
                field: (["短段", "另段"] if field == "body" else "短文")
                for field in gate.COPY_FIELDS
            })),
            ("kana", lambda v: v["verifiedCopy"].update(summary="合成" + "ア" * 9)),
        )
        for reason, mutate in cases:
            with self.subTest(reason=reason):
                packet, value = structured_fixture()
                mutate(value)
                original_representation = copy.deepcopy(value)
                original_representation["verifiedCopy"]["body"] = "\n\n".join(value["verifiedCopy"]["body"])
                self.assertIsNone(gate.BASE["valid_output"](packet, original_representation))
                try:
                    canonical = NAMESPACE["canonical_copy_output"](value)
                except ValueError:
                    self.assertEqual(reason, "missing-copy")
                else:
                    self.assertIsNone(NAMESPACE["valid_output"](packet, canonical))

    def test_unsupported_schema_is_not_retried_with_unconstrained_json(self):
        schema = NAMESPACE["copy_output_schema"](packet_fixture())
        failure = urllib.error.HTTPError("http://127.0.0.1:11434/api/generate", 400, "synthetic unsupported schema", {}, None)
        with patch.object(urllib.request, "urlopen", side_effect=failure) as response:
            with self.assertRaises(urllib.error.HTTPError):
                NAMESPACE["ollama_json"]("NON-NEWS SYNTHETIC TEST", schema=schema)
        response.assert_called_once()


if __name__ == "__main__":
    unittest.main()

