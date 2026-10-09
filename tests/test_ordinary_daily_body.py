"""Synthetic ordinary-copy quality checks; no model, network or news writes."""
import copy
import json
from pathlib import Path
import re
import unittest

import test_source_selection_budget as budget


class OrdinaryDailyBodyTests(unittest.TestCase):
    def setUp(self):
        self.module = budget.load_synthetic_module()
        self.packet = budget.packet(budget.candidate("world"))

    def test_trial_default_schema_and_prompt_stay_unchanged(self):
        default = self.module.copy_output_schema(self.packet)
        self.assertEqual(default["properties"]["verifiedCopy"]["properties"]["body"]["items"]["pattern"], self.module.TARGET_COPY_PATTERN)
        self.assertEqual(default, self.module.copy_output_schema(self.packet, daily_ready=False))
        self.assertEqual(self.module.model_prompt(self.packet), self.module.model_prompt(self.packet, daily_ready=False))
        self.assertNotIn("正常新聞稿亦須可用於 Daily", self.module.model_prompt(self.packet))

    def test_ordinary_body_pattern_is_literal_supported_bounded_repetition(self):
        schema = self.module.copy_output_schema(self.packet, daily_ready=True)
        pattern = schema["properties"]["verifiedCopy"]["properties"]["body"]["items"]["pattern"]
        self.assertNotIn("(?", pattern)
        for length in (59, 111, 600):
            self.assertIsNone(re.fullmatch(pattern, "中" * length))
        for length in (60, 90, 110):
            self.assertIsNotNone(re.fullmatch(pattern, "中" * length))
        for text in ("A" * 100, "中" * 99 + '"', "中" * 99 + "\\", "中" * 99 + "\n"):
            self.assertIsNone(re.fullmatch(pattern, text))
        self.assertEqual(schema["properties"]["verifiedCopy"]["properties"]["body"]["minItems"], 2)
        self.assertEqual(schema["properties"]["verifiedCopy"]["properties"]["body"]["maxItems"], 2)

    def test_visible_body_boundaries_and_short_world_manu_shapes(self):
        for length in (59, 95, 99, 1801):
            self.assertFalse(self.module.daily_body_ready({"body": "中" * length}))
        for length in (100, 120, 1800):
            self.assertTrue(self.module.daily_body_ready({"body": "中" * length}))
        value = {"body": "中" * 49 + " " * 200 + "\n\n" + "文" * 50}
        before = copy.deepcopy(value)
        self.assertFalse(self.module.daily_body_ready(value))
        self.assertEqual(value, before)

    def test_other_copy_fields_cannot_satisfy_body_floor(self):
        value = {field: "中" * 150 for field in self.module.producer.COPY_FIELDS}
        value["body"] = "中" * 95
        self.assertFalse(self.module.daily_body_ready(value))

    def test_final_trusted_prompt_requires_grounding_and_no_padding(self):
        prompt = self.module.model_prompt(self.packet, daily_ready=True)
        tail = prompt.split("END_INPUT\n", 1)[1]
        for term in ("至少100", "最多1800", "來源支持", "填充", "來源不足時不得編造"):
            self.assertIn(term, tail)

    def test_workflow_requires_daily_ready_copy_for_trial_and_ordinary_production(self):
        workflow = (budget.ROOT / ".github/workflows/general-news-producer.yml").read_text(encoding="utf-8")
        helper = (budget.ROOT / "scripts/parallel_general_news_fallback.py").read_text(encoding="utf-8")
        self.assertIn('"--daily-ready-copy"', helper)
        self.assertIn("python -u scripts/parallel_general_news_fallback.py worker", workflow)
        self.assertIn('timeout --signal=KILL "${fallback_seconds}s"', workflow)
        self.assertEqual(workflow.count("python -u scripts/parallel_general_news_fallback.py worker"), 1)

    def test_larger_model_contract_preserves_spent_predecessor_and_strict_gates(self):
        import sys
        sys.path.insert(0, str(budget.ROOT / "scripts"))
        import editorial_revision_trial as trial
        self.assertEqual(trial.PREDECESSOR_CONTRACT, "07c723dc652c32b51237c599fd082e8eb518dba75cf40ca565a658185ca5c1b1")
        self.assertNotEqual(trial.CONTRACT_REVISION, trial.PREDECESSOR_CONTRACT)
        self.assertEqual(trial.CONTRACT["model"], "gemma3:4b-it-qat")
        self.assertEqual(trial.CONTRACT["ownerPolicy"], "non-China-developed-models-only")
        self.assertFalse(trial.CONTRACT["nativeSystemRole"])
        self.assertEqual(trial.CONTRACT["dailyBody"]["visibleMinimum"], 100)
        self.assertEqual(trial.CONTRACT["sourceSelection"]["maxModelCalls"], 3)
        self.assertEqual(trial.CONTRACT["gatePolicy"], "existing-valid-output-and-canonical-merge-unchanged")
        self.assertTrue(trial.reviewed_code(budget.ROOT))

    def test_existing_runner_resources_are_checked_before_larger_model_pull(self):
        workflow = (budget.ROOT / ".github/workflows/general-news-producer.yml").read_text(encoding="utf-8")
        self.assertIn("ollama-google-gemma3-4b-qat-b0313423c944-v1", workflow)
        self.assertIn("LOCAL_MODEL_RESOURCES_INSUFFICIENT", workflow)
        self.assertLess(workflow.index("LOCAL_MODEL_RESOURCES_INSUFFICIENT"), workflow.index("ollama pull gemma3:4b-it-qat"))
        self.assertNotIn("ollama pull qwen2.5:1.5b", workflow)

    def test_short_model_body_is_rejected_without_writes_and_same_call_budget(self):
        harness = budget.SourceSelectionBudgetTests()
        harness.setUp()
        def short(source, options):
            value = budget.structured_copy(source)
            value["verifiedCopy"]["body"] = ["中" * 47, "文" * 48]
            return value
        result = harness.run_main(budget.request(["world", "asia", "hong-kong"]), harness.good_source, short, daily_ready=True)
        self.assertEqual(result.writes, [])
        self.assertEqual(len(result.models), 3)
        self.assertEqual(result.error, "LOCAL_FALLBACK_NO_VERIFIED_SOURCE_PAGE_COPY")
        self.assertTrue(all(row["stage"] == "daily-body-gate" for row in result.diagnostics))
        self.assertTrue(all(row["bodyVisibleCharacters"] == 95 for row in result.diagnostics))
        self.assertNotIn("中中中", result.output)

    def test_ordinary_complete_copy_preserves_strict_grounding_and_one_per_desk(self):
        harness = budget.SourceSelectionBudgetTests()
        harness.setUp()
        result = harness.run_main(budget.request(["world", "asia", "hong-kong"]), harness.good_source, daily_ready=True)
        self.assertIsNone(result.error)
        self.assertEqual(len(result.models), 3)
        self.assertEqual(len(result.writes), 2)
        self.assertEqual(len(json.loads(result.writes[1])["articles"]), 3)


if __name__ == "__main__":
    unittest.main()
