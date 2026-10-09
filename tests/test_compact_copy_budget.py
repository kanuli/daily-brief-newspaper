"""Synthetic concise copy bounds; no generation or publication writes."""
import copy
import re
import unittest

import test_source_selection_budget as fixtures


class CompactCopyTests(unittest.TestCase):
    def setUp(self):
        self.module = fixtures.load_synthetic_module()
        self.packet = fixtures.packet(fixtures.candidate("world"))
        value = self.module.canonical_copy_output(fixtures.structured_copy(self.packet))
        self.copy = value["verifiedCopy"]
        self.facts = value["facts"]

    def test_complete_compact_copy_passes_without_repair(self):
        before = copy.deepcopy(self.copy)
        self.assertTrue(self.module.compact_copy_ready(self.facts, self.copy))
        self.assertEqual(self.copy, before)
        self.assertTrue(self.module.daily_body_ready(self.copy))

    def test_exact_two_supplied_paragraphs_and_stricter_length_boundaries(self):
        for length in (60, 110):
            value = {**self.copy, "body": "中" * length + "\n\n" + "文" * length}
            self.assertTrue(self.module.compact_copy_ready(self.facts, value))
        for body in ("中" * 59 + "\n\n" + "文" * 60, "中" * 111 + "\n\n" + "文" * 60,
                     "中" * 60, "中" * 60 + "\n\n" + "文" * 60 + "\n\n" + "新" * 60):
            with self.subTest(bodyLength=len(body)):
                self.assertFalse(self.module.compact_copy_ready(self.facts, {**self.copy, "body": body}))

    def test_schema_and_deterministic_field_caps_agree_without_truncation(self):
        schema = self.module.copy_output_schema(self.packet, daily_ready=True)
        for field, maximum in self.module.COMPACT_FIELD_LIMITS.items():
            pattern = schema["properties"]["verifiedCopy"]["properties"][field]["pattern"]
            self.assertIsNotNone(re.fullmatch(pattern, "中" * maximum))
            self.assertIsNone(re.fullmatch(pattern, "中" * (maximum + 1)))
            value = {**self.copy, field: "中" * (maximum + 1)}
            before = copy.deepcopy(value)
            self.assertFalse(self.module.compact_copy_ready(self.facts, value))
            self.assertEqual(value, before)

    def test_fact_count_minimum_and_maximum_are_unchanged_only_upper_length_is_bounded(self):
        schema = self.module.copy_output_schema(self.packet, daily_ready=True)["properties"]["facts"]
        self.assertEqual(schema["minItems"], 2)
        self.assertEqual(schema["maxItems"], 5)
        self.assertEqual(schema["items"]["maxLength"], 100)
        self.assertTrue(self.module.compact_copy_ready(["中" * 100, "文" * 100], self.copy))
        self.assertFalse(self.module.compact_copy_ready(["中" * 101, "文" * 100], self.copy))

    def test_overlong_model_copy_is_rejected_after_original_gates_with_no_files(self):
        harness = fixtures.SourceSelectionBudgetTests(); harness.setUp()
        def overlong(packet, options):
            value = fixtures.structured_copy(packet)
            value["verifiedCopy"]["body"] = ["中" * 111, "文" * 111]
            return value
        harness.module.MAX_MODEL_CALLS = 1
        result = harness.run_main(fixtures.request(["world"]), harness.good_source, overlong, daily_ready=True)
        self.assertEqual(len(result.models), 1)
        self.assertEqual(result.writes, [])
        self.assertEqual(result.diagnostics[0]["stage"], "compact-copy-gate")
        self.assertEqual(result.error, "LOCAL_FALLBACK_NO_VERIFIED_SOURCE_PAGE_COPY")

    def test_source_grounding_instruction_and_original_runtime_limits_are_preserved(self):
        tail = self.module.model_prompt(self.packet, daily_ready=True).split("END_INPUT\n", 1)[1]
        for text in ("兩段", "每段60至110", "不得編造", "不能靠其他欄位字數", "來源支持"):
            self.assertIn(text, tail)
        self.assertEqual(self.module.MAX_MODEL_CALLS, 3)
        self.assertEqual(self.module.MAX_SOURCE_PROBES, 12)
        self.assertEqual(self.module.MODEL_CONTEXT, 32768)
        self.assertEqual(self.module.MAX_RUN_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
