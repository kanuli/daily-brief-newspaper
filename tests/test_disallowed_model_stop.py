"""Owner policy regression checks. No network, inference or cancellation calls."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def step(text, name):
    return text.split("      - name: " + name, 1)[1].split("      - name:", 1)[0]


class DisallowedModelStopTests(unittest.TestCase):
    def test_news_workflow_can_run_only_reviewed_google_model_not_qwen(self):
        text = (ROOT / ".github/workflows/general-news-producer.yml").read_text(encoding="utf-8")
        for name in ("Cache open-source local fallback model", "Run open-source local capacity fallback"):
            block = step(text, name)
            self.assertEqual(block.count("if:"), 1)
            executable = "\n".join(line for line in block.splitlines() if not line.lstrip().startswith("#"))
            self.assertNotIn("qwen", executable.lower())
        self.assertIn("ollama pull gemma3:4b-it-qat", text)
        self.assertNotIn("ollama pull qwen", text)
        self.assertIn("LOCAL_MODEL_IDENTITY_NOT_REVIEWED", text)
        self.assertIn("b0313423c9448adfab711aacbc9d0b885a390eb31f1145d7f8495d1e6f84f257", text)
        self.assertLess(text.index("LOCAL_MODEL_IDENTITY_NOT_REVIEWED"), text.index('timeout --signal=KILL'))

    def test_infrastructure_qwen_claim_restore_run_and_finalization_are_disabled(self):
        text = (ROOT / ".github/workflows/editor-in-chief-newsroom-assignment.yml").read_text(encoding="utf-8")
        for name in ("Site Editor-in-Chief claims bounded infrastructure capability probe",
                     "Restore existing local fallback model for infrastructure probe",
                     "Check repaired dependencies and synthetic local-model readiness only",
                     "Preserve immutable capability history and fresh runtime-only verdict"):
            block = step(text, name)
            self.assertEqual(block.count("if:"), 1)
            self.assertIn("if: ${{ false }}", block)

    def test_stop_cancels_only_the_exact_disallowed_trial_not_other_recovery(self):
        text = (ROOT / ".github/workflows/stop-disallowed-local-model.yml").read_text(encoding="utf-8")
        self.assertIn("const run_id = 37920281031;", text)
        self.assertIn("run.head_sha !== '511fae968eef1e6bed3db3a46ff9c30bb07d74be'", text)
        self.assertIn("run.run_attempt !== 1", text)
        self.assertIn("if (run.status === 'completed')", text)
        self.assertEqual(text.count("cancelWorkflowRun("), 1)
        self.assertNotIn("listWorkflowRuns", text)
        self.assertNotIn("forceCancel", text)


if __name__ == "__main__":
    unittest.main()
