"""Regression tests at the EIC dispatcher and merge boundaries."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from textwrap import dedent
import unittest
from unittest.mock import patch

import build_today_daily_from_desk as daily_builder

from merge_live_into_desk import merge
from scheduled_publication_dispatch import gate
from scheduled_publication_contract import CONTRACT, desk_checkpoint_errors
from test_scheduled_publication_v9 import fixture

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT.parent / "evidence/live_d98185f.json"
ROBOTS = ("desk-merge", "daily-recovery", "pages", "public-probe", "stock")


def plan():
    return {"assignments": [{"robot": robot, "dispatchable": True} for robot in ROBOTS]}


class DispatchIntegrationTests(unittest.TestCase):
    def test_authentic_rejected_payload_is_held_without_leaf_dispatch(self):
        live = json.loads(LIVE.read_bytes())
        original = plan()
        receipt = gate(original, live, {}, {"date": "2026-10-13"})
        self.assertEqual(receipt["status"], "LIVE_CONTRACT_HOLD")
        self.assertEqual(sum("missing timeLabel" in e for e in receipt["liveErrors"]), 9)
        self.assertEqual(receipt["held"], ["desk-merge", "daily-recovery", "pages"])
        self.assertEqual([e["itemIndex"] for e in receipt["fieldErrors"]
                          if e["reason"] == "missing timeLabel"], list(range(9)))
        self.assertEqual([r["robot"] for r in original["assignments"] if r["dispatchable"]],
                         ["public-probe", "stock"])
        self.assertEqual(gate(plan(), live, {}, {})["liveSha256"], receipt["liveSha256"])

    def test_corrected_commit_reopens_only_existing_scoped_assignments(self):
        live, desk = fixture()
        pending = plan()
        receipt = gate(pending, live, desk, {})
        self.assertEqual(receipt["status"], "WAIT_FOR_ROLLING_DESK")
        self.assertEqual(receipt["held"], ["daily-recovery", "pages"])
        accepted, merged = merge(live, desk)
        self.assertEqual(gate(plan(), accepted, merged, {})["status"], "WAIT_FOR_CURRENT_DAILY")
        allowed = plan()
        allowed["assignments"][0]["dispatchable"] = False
        evidence = ROOT.parent / "evidence"
        public_live = json.loads((evidence / "public_live_20261013.json").read_bytes())
        public_desk = json.loads((evidence / "public_desk_20261013.json").read_bytes())
        public_daily = json.loads((evidence / "public_daily_20261013.json").read_bytes())
        clock = datetime.fromisoformat(public_live["lastUpdated"])
        historical_live = dict(public_live, publicationContract=CONTRACT)
        historical_live.pop("coverage")
        accepted, merged = merge(historical_live, public_desk, now=clock)
        receipt = gate(allowed, accepted, merged, public_daily, now=clock)
        self.assertEqual(receipt["status"], "PASS")
        self.assertFalse(allowed["assignments"][0]["dispatchable"])
        public_daily["articles"][0].pop("sourceUrl")
        receipt = gate(plan(), accepted, merged, public_daily, now=clock)
        self.assertEqual(receipt["status"], "WAIT_FOR_VALID_DAILY")
        self.assertIn("missing sourceUrl", receipt["dailyError"])
        self.assertIn("pages", receipt["held"])

    def test_eic_can_release_scheduled_desk_to_daily_without_legacy_draft(self):
        from daily_recovery_dependency import daily_budget, inspect_daily_dependency

        with tempfile.TemporaryDirectory() as name, patch.object(daily_builder, "DATA", Path(name)):
            root = Path(name)
            live, desk, clock, original = self.historical_repair_inputs(root)
            self.assertNotIn("verifiedDraftId", live["coverage"])
            latest = root / "latest.json"
            initial = latest.read_bytes()
            args = dict(now=clock, desk=desk, live=live, builder=daily_builder,
                        integrity_state="CURRENT", integrity_detail={"depthMet": True})

            unready = inspect_daily_dependency(**args)
            self.assertFalse(unready["ready"])
            self.assertIn("DATED_EDITION_HOLD", unready.get("detail", ""))

            (root / "2026-10-13.json").write_bytes(original)
            verified = inspect_daily_dependency(**args)
            self.assertTrue(verified["ready"], verified)
            self.assertEqual(verified["datedSourceSha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(latest.read_bytes(), initial)
            state, decision = daily_budget({}, verified)
            self.assertTrue(decision["dispatchable"])
            self.assertEqual(state["epochs"][0]["dispatchesUsed"], 0)

            # A legitimate date advance uses the normal builder and its existing
            # material-selection budget, still without a legacy Producer draft.
            latest.write_text(json.dumps({"date": "2026-10-12"}), encoding="utf-8")
            advanced = inspect_daily_dependency(**args)
            self.assertTrue(advanced["ready"], advanced)
            self.assertNotIn("datedSourceSha256", advanced)

    def test_publisher_preflight_requires_explicit_contract_marker(self):
        live = fixture()[0]
        del live["publicationContract"]
        with tempfile.TemporaryDirectory() as name:
            draft = Path(name) / "draft.json"
            draft.write_text(json.dumps(live), encoding="utf-8")
            run = subprocess.run([sys.executable, "-B",
                                  str(ROOT / "scripts/scheduled_publication_contract.py"), str(draft)],
                                 capture_output=True, timeout=20)
        self.assertEqual(run.returncode, 1, run.stdout)
        self.assertIn(b"publicationContract", run.stderr)

    def test_stuck_desk_merge_requires_changed_verified_input(self):
        from newsroom_control_plane import apply_previous_outcomes

        now = datetime(2026, 10, 13, 10, tzinfo=timezone.utc)
        old = dict(scheduledLive=True, liveLastUpdated=(now - timedelta(hours=1)).isoformat(),
                   scheduledLiveInputSha256="older")
        previous = {"assignments": [{"robot": "desk-merge", "mode": "normal",
                                      "status": "stuck", "attempt": 3, "outcomeBefore": old}]}
        for digest, permitted in (("older", False), (None, False), ("new verified material", True)):
            with self.subTest(current=digest):
                draft = {"robot": "desk-merge", "workflow": "merge-live-into-desk.yml",
                         "status": "assigned", "dispatchable": True}
                current = dict(scheduledLive=True, liveLastUpdated=now.isoformat(),
                               scheduledLiveInputSha256=digest)
                apply_previous_outcomes([draft], {"desk-merge": {}}, previous, current,
                                        now=now, trigger_robot=None)
                self.assertEqual(draft["dispatchable"], permitted)
                self.assertEqual(draft["attempt"], 1 if permitted else 3)

    def test_current_date_only_daily_blocks_pages_dispatch(self):
        live, desk = fixture()
        accepted, merged = merge(live, desk)
        pending = plan()
        receipt = gate(pending, accepted, merged, {"date": live["date"]})
        self.assertEqual(receipt["status"], "WAIT_FOR_VALID_DAILY")
        self.assertFalse(receipt["dailyCurrent"])
        self.assertIn("pages", receipt["held"])
        self.assertFalse(next(row for row in pending["assignments"] if row["robot"] == "pages")["dispatchable"])
        self.assertTrue(next(row for row in pending["assignments"] if row["robot"] == "daily-recovery")["dispatchable"])
        broken_date = gate(plan(), accepted, merged, {"date": [live["date"]]})
        self.assertEqual(broken_date["status"], "WAIT_FOR_CURRENT_DAILY")
        self.assertIn("pages", broken_date["held"])

    def test_same_date_corrupt_daily_requires_recovery_authorization(self):
        original = (ROOT.parent / "evidence/public_daily_20261013.json").read_bytes()
        edition = json.loads(original)
        clock = datetime.fromisoformat("2026-10-13T19:12:00+08:00")
        with tempfile.TemporaryDirectory() as name, patch.object(daily_builder, "DATA", Path(name)):
            latest = Path(name) / "latest.json"
            latest.write_bytes(original)
            valid, outcome = daily_builder.build(now=clock)
            self.assertEqual(valid, edition)
            self.assertFalse(outcome["changed"])
            self.assertEqual(latest.read_bytes(), original)
            malformed = json.dumps({"date": edition["date"]}).encode()
            latest.write_bytes(malformed)
            with self.assertRaisesRegex(SystemExit, "DAILY_SAME_DATE_REPAIR_AUTHORIZATION_HOLD"):
                daily_builder.build(now=clock)
            self.assertEqual(latest.read_bytes(), malformed)

    def historical_repair_inputs(self, data):
        base = ROOT.parent / "evidence"
        live = json.loads((base / "public_live_20261013.json").read_bytes())
        desk = json.loads((base / "public_desk_20261013.json").read_bytes())
        clock = datetime.fromisoformat(live["lastUpdated"])
        live["publicationContract"] = CONTRACT
        live.pop("coverage")
        live, desk = merge(live, desk, now=clock)
        for filename, value in (("live.json", live), ("desk-latest.json", desk), ("latest.json", {"date": live["date"]})):
            (data / filename).write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        raw_daily = (base / "public_daily_20261013.json").read_bytes()
        return live, desk, clock, raw_daily

    def test_eic_repairs_latest_from_verified_dated_edition_once(self):
        with tempfile.TemporaryDirectory() as name, patch.object(daily_builder, "DATA", Path(name)):
            root = Path(name)
            live, desk, clock, original = self.historical_repair_inputs(root)
            latest = root / "latest.json"
            initial = latest.read_bytes()
            dated = root / "2026-10-13.json"
            topic = root / "topic-more"
            topic.mkdir()
            related = topic / dated.name
            related.write_bytes(b'{"independent":"topic copy"}')
            check_plan = plan()
            eic = gate(check_plan, live, desk, json.loads(initial), now=clock)
            self.assertIn("pages", eic["held"])
            self.assertTrue(next(row for row in check_plan["assignments"] if row["robot"] == "daily-recovery")["dispatchable"])
            with self.assertRaisesRegex(SystemExit, "DAILY_SAME_DATE_DATED_EDITION_HOLD"):
                daily_builder.build(now=clock, restore_invalid_current=True)
            self.assertEqual(latest.read_bytes(), initial)

            dated.write_bytes(original)
            edition, decision = daily_builder.build(now=clock, restore_invalid_current=True)
            self.assertEqual(decision["datedSourceSha256"], hashlib.sha256(original).hexdigest())
            self.assertEqual(edition, json.loads(original))
            latest.write_bytes(initial + b" ")
            with self.assertRaisesRegex(SystemExit, "DAILY_SAME_DATE_INPUT_CHANGED_HOLD"):
                daily_builder.write_recovered_daily(edition, decision)
            self.assertEqual(latest.read_bytes(), initial + b" ")
            latest.write_bytes(initial)
            dated.write_bytes(original + b" ")
            with self.assertRaisesRegex(SystemExit, "DAILY_SAME_DATE_INPUT_CHANGED_HOLD"):
                daily_builder.write_recovered_daily(edition, decision)
            dated.write_bytes(original)

            daily_builder.write_recovered_daily(edition, decision)
            self.assertEqual(latest.read_bytes(), original)
            self.assertEqual(dated.read_bytes(), original)
            self.assertEqual(related.read_bytes(), b'{"independent":"topic copy"}')
            repeated, next_decision = daily_builder.build(now=clock, restore_invalid_current=True)
            self.assertEqual(repeated, edition)
            self.assertFalse(next_decision["changed"])
            self.assertEqual(gate(plan(), live, desk, repeated, now=clock)["status"], "PASS")

    def test_workflow_marks_same_date_change_once_by_blob(self):
        git = shutil.which("git")
        bash = Path(git).parent.parent / "bin/bash.exe" if os.name == "nt" else shutil.which("bash")
        if not bash or not Path(bash).is_file():
            self.skipTest("Git Bash required for workflow shell regression")
        path = ROOT / ".github/workflows/daily-today-recovery.yml"
        source = path.read_text(encoding="utf-8")
        step = source.split("        id: build", 1)[1].split("      - name: Validate recovered Daily", 1)[0]
        block = step.split("        run: |\n", 1)[1].replace("/tmp/daily-recovery.json", '"$RECOVERY_TEST_LOG"')
        launcher = """python() {
    if [ "$1" = scripts/build_today_daily_from_desk.py ]; then
        "$RECOVERY_PYTHON" "$@" --now "$RECOVERY_CLOCK"
    else
        "$RECOVERY_PYTHON" "$@"
    fi
}
"""
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            data = root / "data"
            data.mkdir()
            shutil.copytree(ROOT / "scripts", root / "scripts")
            _, _, clock, original = self.historical_repair_inputs(data)
            (data / "2026-10-13.json").write_bytes(original)
            env = dict(os.environ, RECOVERY_PYTHON=Path(sys.executable).as_posix(), RECOVERY_CLOCK=clock.isoformat(),
                       RECOVERY_TEST_LOG=(root / "build.json").as_posix())
            for index, expected in enumerate(("true", "false")):
                output = root / f"outputs-{index}"
                env["GITHUB_OUTPUT"] = output.as_posix()
                q = subprocess.run([str(bash), "-c", launcher + dedent(block)], cwd=root, env=env,
                                   capture_output=True, text=True, timeout=24)
                self.assertEqual(q.returncode, 0, q.stderr)
                self.assertEqual(output.read_text(encoding="utf-8").splitlines(),
                                 ["before=2026-10-13", "after=2026-10-13", f"changed={expected}"])
            self.assertEqual((data / "latest.json").read_bytes(), original)
        self.assertIn("steps.build.outputs.changed == 'true' && steps.persist.outputs.daily_persisted == 'true'", source)

    def test_checkpoint_incomplete_when_retained_timestamp_is_in_future(self):
        live, desk = fixture()
        later = datetime.now(timezone.utc) + timedelta(hours=1)
        desk["desks"]["world"][0]["publishedAt"] = later.isoformat()
        published, merged = merge(live, desk)
        self.assertFalse(published["coverage"]["deskFreshnessMet"])
        self.assertEqual(published["coverage"]["status"], "INCOMPLETE")
        self.assertFalse(published["coverage"]["publishingGateMet"])
        self.assertTrue(desk_checkpoint_errors(published, merged))

    def test_command_used_by_eic_preserves_failed_contract_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for filename, obj in (("plan", plan()), ("desk", {}), ("daily", {"date": "2026-10-13"})):
                (root / f"{filename}.json").write_text(json.dumps(obj), encoding="utf-8")
            proc = subprocess.run([sys.executable, "-B", "scripts/scheduled_publication_dispatch.py",
                "--plan", str(root / "plan.json"), "--live", str(LIVE), "--desk", str(root / "desk.json"),
                "--daily", str(root / "daily.json"), "--receipt", str(root / "receipt.json"), "--commit", "a"*40],
                cwd=ROOT, capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            updated = json.loads((root / "plan.json").read_bytes())
            receipt = json.loads((root / "receipt.json").read_bytes())
            self.assertEqual(updated["scheduledPublicationDispatch"], receipt)
            self.assertEqual(receipt["status"], "LIVE_CONTRACT_HOLD")
            self.assertEqual(receipt["sourceCommit"], "a"*40)
            self.assertEqual(receipt["liveFileSha256"], hashlib.sha256(LIVE.read_bytes()).hexdigest())

    def test_already_dispatched_exact_phase_is_held_until_changed_or_cooled_down(self):
        live, desk = fixture()
        now = datetime.now(timezone.utc)

        def assignment():
            return {"assignments": [{"robot":"desk-merge", "dispatchable":True,
                                      "assignmentId":"assigned", "workflow":"merge-live-into-desk.yml"}]}

        before = gate(assignment(), live, desk, {}, now=now)
        attempted = {"scheduledPublicationDispatch": before, "execution": [{
            "robot":"desk-merge", "assignmentId":"assigned", "workflow":"merge-live-into-desk.yml",
            "dispatched": True}]}
        duplicate = assignment()
        after = gate(duplicate, live, desk, {}, now=now+timedelta(seconds=30), previous=attempted)
        self.assertFalse(duplicate["assignments"][0]["dispatchable"])
        self.assertIn("scheduled-equivalent-dispatch-cooldown", duplicate["assignments"][0]["blockedBy"])
        restart = assignment()
        gate(restart, live, desk, {}, now=now+timedelta(minutes=2),
             previous={"scheduledPublicationDispatch":after})
        self.assertFalse(restart["assignments"][0]["dispatchable"])
        live["items"][0]["title"] += "更新"
        changed = assignment()
        gate(changed, live, desk, {}, now=now+timedelta(minutes=2), previous=attempted)
        self.assertTrue(changed["assignments"][0]["dispatchable"])
        live["items"][0]["title"] = live["items"][0]["title"].removesuffix("更新")
        cooled = assignment()
        gate(cooled, live, desk, {}, now=now+timedelta(minutes=16), previous=attempted)
        self.assertTrue(cooled["assignments"][0]["dispatchable"])
