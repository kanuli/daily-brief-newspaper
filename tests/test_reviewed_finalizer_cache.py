"""Offline filesystem cache regression; no source/model calls or GitHub writes."""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import editorial_revision_trial as trial


class ReviewedCacheTests(unittest.TestCase):
    def cache(self, root):
        (root / "scripts").mkdir()
        for path in (ROOT / "scripts").glob("*.py"):
            shutil.copyfile(path, root / "scripts" / path.name)
        workflow = Path(".github/workflows/general-news-producer.yml")
        (root / workflow).parent.mkdir(parents=True)
        shutil.copyfile(ROOT / workflow, root / workflow)

    def test_both_checkouts_preserve_all_modules_and_preflight_before_work(self):
        workflow = (ROOT / ".github/workflows/general-news-producer.yml").read_text()
        self.assertEqual(workflow.count("cp scripts/*.py /tmp/eic-editorial-reviewed/scripts/"), 2)
        self.assertEqual(workflow.count('assert reviewed_code(Path("/tmp/eic-editorial-reviewed"))'), 2)
        prepare_check = workflow.index("REVIEWED_CACHE_INCOMPLETE")
        self.assertLess(prepare_check, workflow.index("Load the latest discovery reservoir"))
        final_check = workflow.rindex("REVIEWED_CACHE_INCOMPLETE")
        self.assertLess(final_check, workflow.index("Validate bounded fragments before unchanged canonical merge"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.cache(root)
            self.assertTrue(trial.reviewed_code(root))
            # Actual finalizer omissions: reviewed helper and transitive import.
            self.assertTrue((root / "scripts/verified_draft_pending.py").is_file())
            self.assertTrue((root / "scripts/desk_freshness_policy.py").is_file())
            self.assertTrue((root / "scripts/owned_general_news_runtime.py").is_file())

    def test_missing_reviewed_helper_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.cache(root)
            (root / "scripts/verified_draft_pending.py").unlink()
            self.assertFalse(trial.reviewed_code(root))

    def test_changed_cached_validator_still_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.cache(root)
            (root / "scripts/general_news_verified_producer.py").write_text("# synthetic corruption\n")
            self.assertFalse(trial.reviewed_code(root))

    def test_cache_fix_cannot_mint_another_semantic_attempt(self):
        self.assertEqual(trial.CONTRACT_REVISION, "929e6c34cb8ba78a4de0c4ba76957f281055866f788b28de6bc81ee27b3f492d")
        self.assertEqual(trial.MAX_RUNTIME_MINUTES, 20)
        self.assertEqual(trial.CONTRACT["execution"]["maxSourceProbesPerWorker"], 4)
        self.assertEqual(trial.CONTRACT["execution"]["maxModelCallsPerWorker"], 1)


if __name__ == "__main__":
    unittest.main()
