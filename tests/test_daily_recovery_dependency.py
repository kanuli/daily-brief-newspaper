import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_today_daily_from_desk as builder
import validate_desk_integrity as integrity
from daily_recovery_dependency import daily_budget, inspect_daily_dependency

NOW = datetime(2026, 10, 9, 4, 0, tzinfo=timezone.utc)
TARGET = "2026-10-09"


def story(slug, index):
    return {
        "id": f"{slug}-fixture-{index}", "desk": slug,
        "title": "測試新聞", "dek": "測試導言", "summary": "測試摘要",
        "body": "合法測試內容" * 12 + "\n\n" + "來源測試內容" * 12,
        "context": "測試背景", "why": "測試影響", "watchNext": "測試後續",
        "sourceName": "Fixture", "sourceUrl": f"https://example.invalid/{slug}/{index}",
        "sources": [{"name": "Fixture", "url": f"https://example.invalid/{slug}/{index}", "facts": ["fixture"]}],
        "timeLabel": "10月09日 11:00 HKT", "publishedAt": (NOW - timedelta(hours=1)).isoformat(),
    }


class DailyDependencyTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.data = Path(self.directory.name)
        self.old_data = builder.DATA
        builder.DATA = self.data
        self.desk = {
            "date": TARGET, "generatedAt": NOW.isoformat(),
            "desks": {slug: [story(slug, index) for index in range(floor)] for slug, floor in integrity.FLOORS.items()},
        }
        self.live = {
            "lastUpdated": NOW.isoformat(),
            "coverage": {
                "status": "COMPLETE", "sourceGateMet": True, "copyGateMet": True,
                "routingGateMet": True, "publishingGateMet": True,
                "verifiedDraftId": "verified-source-fixture", "verifiedDraftCreatedAt": (NOW - timedelta(minutes=1)).isoformat(),
            },
        }
        self.previous_daily = {"date": "2026-10-08", "editionNumber": "001"}

    def tearDown(self):
        builder.DATA = self.old_data
        self.directory.cleanup()

    def inspect(self):
        for name, value in (("desk-latest.json", self.desk), ("live.json", self.live), ("latest.json", self.previous_daily)):
            (self.data / name).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        before = (self.data / "latest.json").read_bytes()
        state, detail = integrity.inspect(self.data / "desk-latest.json", self.data / "live.json")
        evidence = inspect_daily_dependency(now=NOW, desk=self.desk, live=self.live, builder=builder, integrity_state=state, integrity_detail=detail)
        self.assertEqual(before, (self.data / "latest.json").read_bytes())
        self.assertFalse((self.data / f"{TARGET}.json").exists())
        return evidence

    def classify(self, previous=None, structural=False, producer_ready=False):
        import newsroom_control_plane as control
        # Synthetic isolated DATA only. Production continues to use the
        # unchanged canonical builder and repository DATA directory.
        fixtures = {
            "desk": self.desk, "live": self.live, "latest": self.previous_daily,
            "staging": {"lastSearchAt": NOW.isoformat(), "desks": {}},
            "freshness": {"desks": {}}, "prepublish": {}, "producer-capacity": {},
            "editor-status": {"validatorAudit": [{"name": "daily-v3", "ok": False}]} if structural else {},
            "sentinel": {}, "pages-status": {"checkedAt": NOW.isoformat(), "match": True},
            "previous-assignments": previous or {},
            "stocks": {"generatedAt": NOW.isoformat(), "lastCheckedAt": NOW.isoformat()},
            "tts": {},
        }
        if producer_ready:
            fixtures["freshness"] = {"desks": {"world": {"fresh": False, "dailySynced": True, "newestAgeHours": 40}}}
            fixtures["staging"]["desks"] = {"world": [{"publishedAt": NOW.isoformat()}]}
            fixtures["producer-capacity"] = {"status": "DEGRADED_LOCAL_FALLBACK"}
        argv = ["newsroom_control_plane.py", "--registry", str(ROOT / "config/newsroom-robots.json")]
        for name, value in fixtures.items():
            path = self.data / (name + ".json")
            path.write_text(json.dumps(value), encoding="utf-8")
            argv.extend(["--" + name, str(path)])
        # Keep canonical builder's unchanged file names in the isolated DATA.
        (self.data / "desk-latest.json").write_text(json.dumps(self.desk), encoding="utf-8")
        output = self.data / "assignment-output.json"
        argv.extend(["--stock-rc", "0", "--publication-rc", "1", "--vocab-rc", "0",
                     "--now", NOW.isoformat(), "--output", str(output)])
        before = (self.data / "latest.json").read_bytes()
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(control.main(), 0)
        self.assertEqual(before, (self.data / "latest.json").read_bytes())
        return json.loads(output.read_text(encoding="utf-8"))

    def test_actual_classifier_unready_daily_cannot_block_new_live_to_desk(self):
        self.desk["generatedAt"] = (NOW - timedelta(days=1)).isoformat()
        result = self.classify()
        rows = {row["robot"]: row for row in result["assignments"]}
        self.assertFalse(rows["daily-recovery"]["dispatchable"])
        self.assertEqual(rows["daily-recovery"]["status"], "awaiting-daily-prerequisite")
        self.assertTrue(rows["desk-merge"]["dispatchable"])
        self.assertNotIn("daily-recovery", rows["desk-merge"].get("blockedBy", []))

    def test_isolated_production_cannot_starve_a_new_live_desk_checkpoint(self):
        self.desk["generatedAt"] = (NOW - timedelta(days=1)).isoformat()
        result = self.classify(producer_ready=True)
        rows = {row["robot"]: row for row in result["assignments"]}
        self.assertIs(rows["general-producer"]["dispatchable"], True)
        self.assertIs(rows["desk-merge"]["dispatchable"], True)
        self.assertIs(rows["daily-recovery"]["dispatchable"], False)
        self.assertNotIn("general-producer", rows["desk-merge"].get("blockedBy", []))
        self.assertIs(result["healthy"], False)

    def test_real_main_writers_still_exclude_desk_merge(self):
        import newsroom_control_plane as control
        for writer in ("live-publisher", "daily-recovery"):
            with self.subTest(writer=writer):
                desk_row = {"robot": "desk-merge", "status": "assigned", "dispatchable": True}
                rows = [desk_row, {"robot": writer, "status": "assigned", "dispatchable": True},
                        {"robot": "general-producer", "status": "assigned", "dispatchable": True}]
                control.block_downstream_races(rows)
                self.assertEqual(desk_row["blockedBy"], [writer])
                self.assertIs(desk_row["dispatchable"], False)
                self.assertEqual(desk_row["status"], "blocked")

    def test_canonical_producer_git_writes_are_isolated(self):
        text = (ROOT / ".github/workflows/general-news-producer.yml").read_text(encoding="utf-8")
        pushes = [line.strip() for line in text.splitlines() if "git push" in line]
        self.assertEqual(pushes, ["if git push origin HEAD:prepublish-news; then"])
        self.assertIn('git checkout -B prepublish-news origin/prepublish-news', text)
        self.assertIn('-f branch="prepublish-news"', text)

    def test_actual_classifier_budget_survives_confirmed_and_held_cycles(self):
        result = self.classify()
        row = next(row for row in result["assignments"] if row["robot"] == "daily-recovery")
        self.assertTrue(row["dispatchable"])
        result["dailyRecoveryInput"]["epochs"][0]["dispatchesUsed"] = 2
        result["execution"] = [{"robot": "daily-recovery", "assignmentId": row["assignmentId"], "dispatched": True}]
        held = self.classify(result)
        held_row = next(row for row in held["assignments"] if row["robot"] == "daily-recovery")
        self.assertFalse(held_row["dispatchable"])
        self.assertEqual(held_row["status"], "stuck")
        held["execution"] = [{"robot": "daily-recovery", "assignmentId": held_row["assignmentId"], "dispatched": False}]
        again = self.classify(held)
        self.assertEqual(again["dailyRecoveryInput"]["epochs"][0]["dispatchesUsed"], 3)
        self.assertFalse(next(row for row in again["assignments"] if row["robot"] == "daily-recovery")["dispatchable"])

    def test_actual_classifier_current_structural_fault_requests_honest_replan(self):
        self.previous_daily["date"] = TARGET
        result = self.classify(structural=True)
        row = next(row for row in result["assignments"] if row["robot"] == "daily-recovery")
        self.assertFalse(row["dispatchable"])
        self.assertTrue(row["requiresEditorReplan"])
        self.assertEqual(row["status"], "stuck")
        self.assertEqual(row["blockedBy"], [])
        self.assertIn("structural-fault-not-repairable", row["reason"])

    def test_initial_unready_legacy_pool_cannot_get_budget_from_clock_only_readiness(self):
        old = NOW - timedelta(days=3)
        self.desk["date"] = "2026-10-06"
        self.desk["generatedAt"] = old.isoformat()
        self.live["lastUpdated"] = old.isoformat()
        self.live["coverage"]["verifiedDraftCreatedAt"] = old.isoformat()
        for rows in self.desk["desks"].values():
            for row in rows:
                row["publishedAt"] = old.isoformat()
        before = self.inspect()
        self.assertFalse(before["ready"])
        state, _ = daily_budget({"assignments": [{"robot": "daily-recovery", "attempt": 3}]}, before)
        # Only dates/times change; the source/copy reservoir is identical.
        self.desk["date"] = TARGET
        self.desk["generatedAt"] = NOW.isoformat()
        self.live["lastUpdated"] = NOW.isoformat()
        self.live["coverage"]["verifiedDraftCreatedAt"] = (NOW - timedelta(minutes=1)).isoformat()
        for rows in self.desk["desks"].values():
            for row in rows:
                row["publishedAt"] = (NOW - timedelta(hours=1)).isoformat()
        current = self.inspect()
        self.assertTrue(current["ready"])
        state, decision = daily_budget({"dailyRecoveryInput": state}, current)
        self.assertFalse(decision["dispatchable"])
        self.assertEqual(len(state["epochs"]), 1)
        self.assertEqual(state["epochs"][0]["dispatchesUsed"], 3)

    def test_ready_uses_real_builder_and_never_writes_news(self):
        evidence = self.inspect()
        self.assertTrue(evidence["ready"], evidence)
        self.assertEqual(evidence["selectedCount"], 18)

    def test_diagnostic_compaction_preserves_complete_authoritative_material_pool(self):
        evidence = self.inspect()
        state, _ = daily_budget({}, evidence)
        self.assertEqual(state["epochs"][0]["materialPoolHashes"], evidence["materialPoolHashes"])
        self.assertNotIn("materialPoolHashes", state["lastInputEvidence"])
        self.assertEqual(state["lastInputEvidence"]["materialPoolCount"], len(evidence["materialPoolHashes"]))

    def test_old_daily_does_not_block_new_live_to_desk(self):
        self.desk["date"] = "2026-10-08"
        self.desk["generatedAt"] = (NOW - timedelta(days=1)).isoformat()
        evidence = self.inspect()
        self.assertFalse(evidence["ready"])
        _, decision = daily_budget({}, evidence)
        spec = importlib.util.spec_from_file_location("control_for_daily_test", ROOT / "scripts/newsroom_control_plane.py")
        sys.path.insert(0, str(ROOT / "scripts"))
        control = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(control)
        plan = [dict(robot="daily-recovery", **decision), {"robot": "desk-merge", "dispatchable": True}]
        control.block_downstream_races(plan)
        self.assertTrue(plan[1]["dispatchable"])
        self.desk["date"] = TARGET
        self.desk["generatedAt"] = self.live["lastUpdated"]
        evidence = self.inspect()
        self.assertTrue(evidence["ready"], evidence)
        _, decision = daily_budget({}, evidence)
        self.assertTrue(decision["dispatchable"])

    def test_seven_daily_safe_stories_rejected_even_with_hard_depth(self):
        for slug, rows in self.desk["desks"].items():
            for row in rows:
                row["body"] = "too short"
        for slug, count in (("world", 2), ("asia", 2), ("hong-kong", 2), ("japan", 1)):
            for row in self.desk["desks"][slug][:count]:
                row["body"] = "合法測試內容" * 12 + "\n\n" + "來源測試內容" * 12
        evidence = self.inspect()
        self.assertFalse(evidence["ready"])
        self.assertEqual(evidence["selectedCount"], 7)

    def test_future_current_source_rejected(self):
        self.live["lastUpdated"] = (NOW + timedelta(minutes=1)).isoformat()
        self.desk["generatedAt"] = self.live["lastUpdated"]
        self.assertFalse(self.inspect()["ready"])

    def test_future_story_timestamps_do_not_meet_floor(self):
        for rows in self.desk["desks"].values():
            for row in rows:
                row["publishedAt"] = (NOW + timedelta(hours=1)).isoformat()
        evidence = self.inspect()
        self.assertFalse(evidence["ready"])
        self.assertEqual(evidence["selectedCount"], 0)

    def test_unverified_live_rejected(self):
        self.live["coverage"]["sourceGateMet"] = False
        self.assertFalse(self.inspect()["ready"])

    def test_date_bump_cannot_admit_old_verified_source(self):
        self.live["coverage"]["verifiedDraftCreatedAt"] = (NOW - timedelta(days=1)).isoformat()
        self.assertFalse(self.inspect()["ready"])

    def test_metadata_only_changes_do_not_renew_material_budget(self):
        before = self.inspect()
        state, _ = daily_budget({}, before)
        state["epochs"][0]["dispatchesUsed"] = 3
        self.desk["generatedAt"] = (NOW - timedelta(seconds=1)).isoformat()
        self.live["lastUpdated"] = self.desk["generatedAt"]
        self.desk["headSha"] = "irrelevant-new-head"
        for rows in self.desk["desks"].values():
            for row in rows:
                row["verifiedAt"] = NOW.isoformat()
                row["timeLabel"] = "changed clock label"
        after = self.inspect()
        self.assertTrue(after["ready"], after)
        self.assertEqual(before["inputKey"], after["inputKey"])
        _, decision = daily_budget({"dailyRecoveryInput": state, "assignments": [], "execution": []}, after)
        self.assertFalse(decision["dispatchable"])

    def test_published_clock_promoting_existing_unselected_story_cannot_renew(self):
        before = self.inspect()
        state, _ = daily_budget({}, before)
        state["epochs"][0]["dispatchesUsed"] = 3
        self.desk["desks"]["world"][2]["publishedAt"] = (NOW - timedelta(minutes=30)).isoformat()
        after = self.inspect()
        self.assertTrue(after["ready"], after)
        self.assertNotEqual(before["inputKey"], after["inputKey"])
        self.assertEqual(before["materialPoolHashes"], after["materialPoolHashes"])
        state, decision = daily_budget({"dailyRecoveryInput": state}, after)
        self.assertFalse(decision["dispatchable"])
        self.assertEqual(state["activeInputKey"], before["inputKey"])
        self.assertEqual(len(state["epochs"]), 1)

    def test_removal_promoting_existing_story_cannot_renew(self):
        rows = self.desk["desks"]["world"]
        rows.append(story("world", len(rows)))
        before = self.inspect()
        state, _ = daily_budget({}, before)
        state["epochs"][0]["dispatchesUsed"] = 3
        del rows[0]
        after = self.inspect()
        self.assertTrue(after["ready"], after)
        self.assertNotEqual(before["inputKey"], after["inputKey"])
        self.assertTrue(set(after["selectedMaterialHashes"]) <= set(before["materialPoolHashes"]))
        state, decision = daily_budget({"dailyRecoveryInput": state}, after)
        self.assertFalse(decision["dispatchable"])
        self.assertEqual(state["activeInputKey"], before["inputKey"])
        self.assertEqual(len(state["epochs"]), 1)

    def test_id_only_rename_cannot_renew_material_budget(self):
        before = self.inspect()
        state, _ = daily_budget({}, before)
        state["epochs"][0]["dispatchesUsed"] = 3
        self.desk["desks"]["world"][0]["id"] = "new-id-same-source-and-copy"
        after = self.inspect()
        self.assertTrue(after["ready"], after)
        self.assertNotEqual(before["inputKey"], after["inputKey"])
        self.assertEqual(before["materialPoolHashes"], after["materialPoolHashes"])
        self.assertEqual(before["selectedMaterialHashes"], after["selectedMaterialHashes"])
        state, decision = daily_budget({"dailyRecoveryInput": state}, after)
        self.assertFalse(decision["dispatchable"])
        self.assertEqual(state["activeInputKey"], before["inputKey"])
        self.assertEqual(len(state["epochs"]), 1)

    def test_held_cycles_preserve_exhausted_legacy_budget(self):
        evidence = self.inspect()
        previous = {"assignments": [{"robot": "daily-recovery", "attempt": 3, "status": "stuck", "assignmentId": "legacy", "outcomeBefore": {"deskGeneratedAt": "old"}}], "execution": [{"robot": "daily-recovery", "assignmentId": "legacy", "dispatched": False}]}
        state, decision = daily_budget(previous, evidence)
        self.assertFalse(decision["dispatchable"])
        for _ in range(4):
            state, decision = daily_budget({"dailyRecoveryInput": state, "assignments": [], "execution": []}, evidence)
            self.assertFalse(decision["dispatchable"])
            self.assertEqual(state["epochs"][0]["dispatchesUsed"], 3)
        self.assertEqual(len(state["legacyAssignmentAudit"]), 1)
        self.assertNotIn("outcomeBefore", state["legacyAssignmentAudit"][0])

    def test_genuine_validated_new_selection_reopens_bounded_normal(self):
        old = self.inspect()
        state, _ = daily_budget({}, old)
        state["epochs"][0]["dispatchesUsed"] = 3
        self.desk["desks"]["world"][0]["body"] += "\n\n有來源支持的新資訊"
        current = self.inspect()
        self.assertTrue(current["ready"])
        self.assertNotEqual(current["inputKey"], old["inputKey"])
        state, decision = daily_budget({"dailyRecoveryInput": state}, current)
        self.assertTrue(decision["dispatchable"])
        self.assertEqual(decision["attempt"], 1)
        self.assertEqual(len(state["epochs"]), 2)
        self.assertEqual(state["epochs"][0]["dispatchesUsed"], 3)
        for index in range(3):
            row = {"robot": "daily-recovery", "dailyInputKey": current["inputKey"], "assignmentId": f"dispatch-{index}"}
            previous = {"dailyRecoveryInput": state, "assignments": [row], "execution": [dict(row, dispatched=True)]}
            state, decision = daily_budget(previous, current)
            # Re-reading the same confirmed execution must not double-charge.
            repeated, _ = daily_budget(dict(previous, dailyRecoveryInput=state), current)
            self.assertEqual(repeated["epochs"][-1]["dispatchesUsed"], index + 1)
        self.assertFalse(decision["dispatchable"])
        self.assertEqual(decision["status"], "stuck")

    def test_unready_changed_input_cannot_reset_old_budget(self):
        evidence = self.inspect()
        state, _ = daily_budget({}, evidence)
        state["epochs"][0]["dispatchesUsed"] = 3
        self.desk["desks"]["world"][0]["body"] += "\n\n有來源支持的新資訊"
        self.live["coverage"]["sourceGateMet"] = False
        changed = self.inspect()
        state, decision = daily_budget({"dailyRecoveryInput": state}, changed)
        self.assertFalse(decision["dispatchable"])
        self.assertEqual(state["activeInputKey"], evidence["inputKey"])
        self.assertEqual(state["epochs"][0]["dispatchesUsed"], 3)
        self.assertEqual(state["epochs"][0]["materialPoolHashes"], evidence["materialPoolHashes"])
        # Unverified input must not consume the later legitimate material
        # admission once the original independent Live gates actually pass.
        self.live["coverage"]["sourceGateMet"] = True
        validated = self.inspect()
        state, decision = daily_budget({"dailyRecoveryInput": state}, validated)
        self.assertTrue(decision["dispatchable"])
        self.assertEqual(decision["attempt"], 1)
        self.assertEqual(len(state["epochs"]), 2)
        self.assertEqual(state["epochs"][0]["dispatchesUsed"], 3)

    def test_return_to_exhausted_old_input_remains_held(self):
        old_desk = copy.deepcopy(self.desk)
        old = self.inspect()
        state, _ = daily_budget({}, old)
        state["epochs"][0]["dispatchesUsed"] = 3
        self.desk["desks"]["world"][0]["body"] += "\n\n有來源支持的新資訊"
        state, decision = daily_budget({"dailyRecoveryInput": state}, self.inspect())
        self.assertTrue(decision["dispatchable"])
        self.desk = old_desk
        state, decision = daily_budget({"dailyRecoveryInput": state}, self.inspect())
        self.assertFalse(decision["dispatchable"])
        self.assertEqual(state["activeInputKey"], old["inputKey"])
        self.assertEqual(state["epochs"][0]["dispatchesUsed"], 3)


if __name__ == "__main__":
    unittest.main()
