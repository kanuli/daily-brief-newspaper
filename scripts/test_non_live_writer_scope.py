"""Verify that existing data writers have a cutover path without Live access."""
import unittest

from non_live_writer_scope import scope_review


class NonLiveCompatibility(unittest.TestCase):
    def test_preserves_separate_daily_stock_and_vocab_data_paths(self):
        for writer, paths in {
            "daily-today-recovery.yml": ["data/latest.json", "data/archive.json", "data/topic-more/2026-11-23.json"],
            "daily-archive-self-heal.yml": ["data/archive.json", "editions/2026-11-23.html"],
            "daily-japanese-vocab.yml": ["data/vocab/latest.json", "data/vocab/2026-11-23.json"],
            "stock-publication-maintenance.yml": ["data/stocks-latest.json"],
        }.items():
            with self.subTest(writer=writer):
                proof = scope_review(writer, [{"filename": path, "status": "modified"} for path in paths])
                self.assertEqual(proof["confirmedProposedPaths"], sorted(paths))
                self.assertFalse(proof["writeAuthorized"])

    def test_mixed_legacy_live_code_changes_and_rename_do_not_pass(self):
        for path, status, extras in [
            ("data/live.json", "modified", {}),
            ("data/LIVE.json", "modified", {}),
            ("scripts/rolling_news_collector.py", "modified", {}),
            ("data/stocks-latest.json", "renamed", {"previous_filename": "data/live.json"}),
            ("data/stocks-latest.json", "removed", {}),
        ]:
            with self.subTest(path=path, status=status), self.assertRaises(ValueError):
                scope_review("stock-publication-maintenance.yml", [dict(filename=path, status=status, **extras)])

    def test_traversal_invalid_calendar_and_unknown_workflow_do_not_pass(self):
        for writer, path in [
            ("daily-japanese-vocab.yml", "data/vocab/../live.json"),
            ("daily-japanese-vocab.yml", "data/vocab/2026-11-31.json"),
            ("unknown.yml", "data/stocks-latest.json"),
        ]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                scope_review(writer, [dict(filename=path, status="added")])


if __name__ == "__main__":
    unittest.main()
