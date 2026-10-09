"""Synthetic owner-merge fixtures; no actual news, network or file writes."""
import ast
import copy
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def merger():
    path = ROOT / "scripts/merge_live_into_desk.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [n for n in tree.body if not (isinstance(n, ast.ImportFrom) and n.module == "atomic_publish")]
    module = types.ModuleType("synthetic_merger")
    module.__file__ = str(path)
    exec(compile(tree, str(path), "exec"), module.__dict__)
    return module


def story(slug, index):
    value = {k: "合成測試文字" for k in ("dek", "summary", "context", "why", "watchNext", "section", "sectionLabel")}
    value.update(id=f"synthetic-{slug}-{index}", title=f"合成稿件-{slug}-{index}",
                 body="合成正文甲" * 20 + "\n\n" + "合成正文乙" * 20,
                 desk=slug, deskSlugs=[slug], publishedAt="2026-10-10T00:00:00+08:00",
                 verifiedAt="2026-10-10T00:01:00+08:00", timeLabel="合成時間",
                 sourceName="Synthetic Fixture", sourceUrl="https://example.invalid/test")
    return value


class RetainedBodyQuarantineTests(unittest.TestCase):
    def setUp(self):
        self.m = merger()
        self.desk = {"desks": {slug: [story(slug, i) for i in range(floor)] for slug, floor in self.m.FLOORS.items()}}
        self.live = {"date": "2026-10-10", "lastUpdated": "2026-10-10T00:05:00+08:00", "mode": "LIVE", "items": [story("world", "new")], "coverage": {"sourceGateMet": True}}

    def run_merge(self, desk=None, live=None):
        writes = []
        with patch.object(self.m, "load", side_effect=lambda p: copy.deepcopy((live or self.live) if p == self.m.LIVE else (desk or self.desk))), \
             patch.object(self.m, "keep_on_desk", return_value=True), \
             patch.object(self.m, "routed_slugs", side_effect=lambda row: row.get("deskSlugs", [])), \
             patch.object(self.m, "atomic_write_json", create=True, side_effect=lambda p, v: writes.append((p, copy.deepcopy(v)))):
            try:
                self.m.main()
            except SystemExit:
                return writes, False
        return writes, True

    def test_one_bad_old_body_is_preserved_exactly_outside_public_desk(self):
        bad = story("world", "bad")
        bad["body"] = "短文甲" * 13 + "\n\n" + "短文乙" * 13
        original = copy.deepcopy(bad)
        self.desk["desks"]["world"].insert(0, bad)
        writes, ok = self.run_merge()
        self.assertTrue(ok)
        result = dict(writes)[self.m.DESK]
        self.assertNotIn(bad["id"], [s["id"] for s in result["desks"]["world"]])
        self.assertEqual(result["quarantinedStories"][0]["story"], original)
        self.assertEqual(bad, original)
        self.assertTrue(dict(writes)[self.m.LIVE]["coverage"]["publishingGateMet"])

    def test_quarantine_never_relaxes_depth_floor_or_writes_partial_desk(self):
        self.desk["desks"]["japan"][0]["body"] = "太短\n\n太短"
        writes, ok = self.run_merge()
        self.assertFalse(ok)
        self.assertEqual(writes, [])

    def test_short_live_body_is_rejected_not_padded_from_other_fields(self):
        bad = story("world", "bad")
        bad["body"] = "短文甲" * 13 + "\n\n" + "短文乙" * 13
        bad["context"] = "合成長背景" * 200
        before = copy.deepcopy(bad)
        self.assertEqual(self.m.normalize_retained_story(bad), before)
        self.assertEqual(bad, before)
        self.assertTrue(self.m.live_item_rejection_reason(bad))
        self.live["items"].append(bad)
        writes, ok = self.run_merge()
        self.assertTrue(ok)
        self.assertFalse(dict(writes)[self.m.LIVE]["coverage"]["publishingGateMet"])

    def test_repeated_old_invalid_input_does_not_duplicate_quarantine(self):
        bad = story("world", "bad"); bad["body"] = "短\n\n短"
        self.desk["quarantinedStories"] = [{"desk": "world", "story": copy.deepcopy(bad), "reason": "already held"}]
        self.desk["desks"]["world"].append(bad)
        writes, ok = self.run_merge()
        self.assertTrue(ok)
        self.assertEqual(len(dict(writes)[self.m.DESK]["quarantinedStories"]), 1)

    def test_valid_story_copy_source_and_clocks_are_not_rewritten(self):
        before = copy.deepcopy(self.desk["desks"]["japan"])
        writes, ok = self.run_merge()
        self.assertTrue(ok)
        self.assertEqual({s["id"]: s for s in dict(writes)[self.m.DESK]["desks"]["japan"]}, {s["id"]: s for s in before})
        self.assertEqual(self.m.MIN_BODY_MEASURE, 95)

    def test_boundary_cjk_and_non_cjk_measure_matches_original_validator(self):
        for body, accepted in (("字" * 47 + "\n\n" + "字" * 48, True), ("字" * 47 + "\n\n" + "字" * 47, False), ("A" * 47 + "\n\n" + "B" * 48, True)):
            self.assertEqual(not bool(self.m.retained_body_rejection_reason({"body": body})), accepted)


if __name__ == "__main__":
    unittest.main()
