"""Real Git concurrency tests against disposable local remotes."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from textwrap import dedent
import unittest
from unittest.mock import patch

from push_publication_checkpoint import CheckpointHold, push_checkpoint


BASE_LIVE = '{\n  "title": "article A",\n  "verifiedAt": "2026-10-13T11:12:00Z",\n  "leadId": "a",\n  "coverage": null\n}\n'


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = root = Path(temp.name)
        self.bare, self.work, self.writer = [root / name for name in ("bare", "work", "writer")]
        self.git(root, "init", "-q", "--bare", "--initial-branch=main", str(self.bare))
        self.git(root, "clone", "-q", str(self.bare), str(self.writer))
        (self.writer / "data").mkdir()
        self.commit(self.writer, "data/live.json", BASE_LIVE, "publisher A")
        self.git(self.writer, "push", "origin", "HEAD:refs/heads/main")
        self.git(root, "clone", "-q", str(self.bare), str(self.work))
        self.commit(self.work, "data/live.json", BASE_LIVE.replace("null", "10"), "derived coverage for A")

    @staticmethod
    def git(cwd, *args):
        return subprocess.run(["git", "-c", "user.name=Isolated Test", "-c", "user.email=test@example.invalid",
                               "-c", "core.autocrlf=false", *args], cwd=cwd, check=True,
                              capture_output=True, timeout=15).stdout

    def commit(self, cwd, name, value, message):
        (cwd / name).write_bytes(value.encode("utf-8"))
        self.git(cwd, "add", "--", name)
        self.git(cwd, "commit", "-qm", message)

    def update_live(self):
        current = BASE_LIVE.replace("article A", "article B")
        self.commit(self.writer, "data/live.json", current, "publisher B")
        self.git(self.writer, "push", "origin", "HEAD:refs/heads/main")
        return current.encode()

    def test_daily_workflow_dispatch_requires_a_confirmed_new_daily_commit(self):
        path = Path(__file__).resolve().parents[1] / ".github/workflows/daily-today-recovery.yml"
        text = path.read_text(encoding="utf-8")
        persist = text.split("      - name: Commit recovered Daily and archive to main", 1)[1].split(
            "      - name: Dispatch downstream", 1)[0]
        dispatch = text.split("      - name: Dispatch downstream", 1)[1]
        self.assertIn("id: persist", persist)
        self.assertIn("daily_persisted=false", persist)
        self.assertLess(persist.index("python scripts/push_publication_checkpoint.py"),
                        persist.index("daily_persisted=true"))
        self.assertIn("steps.persist.outputs.daily_persisted == 'true'", dispatch)
        self.assertIn("steps.build.outputs.changed == 'true'", dispatch)

    def test_verify_only_is_fail_closed_and_never_pushes(self):
        before = self.git(self.bare, "rev-parse", "main")
        with self.assertRaisesRegex(CheckpointHold, "PUBLICATION_CHECKPOINT_PUSH_UNVERIFIED_HOLD"):
            push_checkpoint(self.work, verify_only=True)
        self.assertEqual(self.git(self.bare, "rev-parse", "main"), before)
        self.assertEqual(push_checkpoint(self.work, pause=lambda _: None), "PUBLISHED")
        once = self.git(self.bare, "rev-parse", "main")
        self.assertEqual(push_checkpoint(self.work, verify_only=True), "ALREADY_PUBLISHED")
        self.git(self.writer, "pull", "--ff-only", "origin", "main")
        self.update_live()
        with self.assertRaisesRegex(CheckpointHold, "PUBLICATION_CHECKPOINT_SUPERSEDED_HOLD"):
            push_checkpoint(self.work, verify_only=True)
        self.assertEqual(self.git(self.bare, "rev-list", "--count", "main").strip(), b"3")
        self.assertNotEqual(self.git(self.bare, "rev-parse", "main"), once)

    def test_daily_dispatch_rechecks_before_each_external_step(self):
        path = Path(__file__).resolve().parents[1] / ".github/workflows/daily-today-recovery.yml"
        source = path.read_text(encoding="utf-8").split("name: Dispatch downstream", 1)[1]
        shell = source.split("      - name: Recovery status", 1)[0]
        guard = "python scripts/push_publication_checkpoint.py --verify-only"
        actions = [line.strip() for line in shell.splitlines()
                   if line.strip().startswith((guard, "gh workflow run "))]
        self.assertEqual(actions, [guard, "gh workflow run pages.yml --ref main",
                                   guard, "gh workflow run discord-notify.yml --ref main -f notification_type=daily"])

    def test_workflow_stops_second_dispatch_if_first_changes_live(self):
        repo = Path(__file__).resolve().parents[1]
        filename = repo / ".github/workflows/daily-today-recovery.yml"
        workflow = filename.read_text(encoding="utf-8").split("name: Dispatch downstream", 1)[1]
        run = workflow.split("        run: |\n", 1)[1].split("      - name: Recovery status", 1)[0]
        git = shutil.which("git")
        bash = Path(git).parent.parent / "bin/bash.exe" if os.name == "nt" else shutil.which("bash")
        if not bash or not Path(bash).is_file():
            self.skipTest("Git Bash is required for the workflow shell regression")
        script = self.work / "scripts/push_publication_checkpoint.py"
        script.parent.mkdir()
        shutil.copyfile(repo / "scripts/push_publication_checkpoint.py", script)
        dispatch_log = self.root / "dispatch.log"
        self.assertEqual(push_checkpoint(self.work, pause=lambda _: None), "PUBLISHED")
        self.git(self.writer, "pull", "--ff-only", "origin", "main")
        self.commit(self.writer, "data/live.json", '{"title":"separate newer Live"}', "publisher B")
        stub = """python() { "$CHECKPOINT_PYTHON" "$@"; }
gh() {
    printf '%s\\n' "$3" >> "$CHECKPOINT_DISPATCH_LOG"
    if [ "$3" = pages.yml ]; then
        git -C "$CHECKPOINT_WRITER" push origin HEAD:refs/heads/main
    fi
}
"""
        env = dict(os.environ, CHECKPOINT_PYTHON=Path(sys.executable).as_posix(),
                   CHECKPOINT_WRITER=self.writer.as_posix(), CHECKPOINT_DISPATCH_LOG=dispatch_log.as_posix())
        result = subprocess.run([str(bash), "-c", stub + dedent(run)], cwd=self.work, env=env,
                                capture_output=True, text=True, timeout=25)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("PUBLICATION_CHECKPOINT_SUPERSEDED_HOLD", result.stderr)
        self.assertEqual(dispatch_log.read_text(encoding="utf-8").splitlines(), ["pages.yml"])
        self.assertEqual(self.git(self.bare, "rev-list", "--count", "main").strip(), b"3")

    def test_desk_or_daily_dependency_change_holds_without_remote_write(self):
        for name in ("data/desk-latest.json", "data/latest.json"):
            with self.subTest(name=name):
                self.commit(self.writer, name, '{"changed":true}', "new publication dependency")
                self.git(self.writer, "push", "origin", "HEAD:refs/heads/main")
                oid = self.git(self.bare, "rev-parse", "main")
                with self.assertRaisesRegex(CheckpointHold, "PUBLICATION_CHECKPOINT_STALE_INPUT_HOLD"):
                    push_checkpoint(self.work, pause=lambda _: None)
                self.assertEqual(self.git(self.bare, "rev-parse", "main"), oid)

    def test_same_date_restore_holds_if_independent_writer_changes_dated_source(self):
        dated = "data/2026-10-13.json"
        self.commit(self.writer, dated, '{"date":"2026-10-13","edition":"verified"}', "original dated edition")
        self.git(self.writer, "push", "origin", "HEAD:refs/heads/main")
        self.git(self.work, "fetch", "origin", "main")
        self.git(self.work, "rebase", "origin/main")
        self.commit(self.work, "data/latest.json", '{"date":"2026-10-13","edition":"verified"}', "restore same-day latest")
        self.commit(self.writer, dated, '{"date":"2026-10-13","edition":"superseded"}', "independent dated edition")
        self.git(self.writer, "push", "origin", "HEAD:refs/heads/main")
        before = self.git(self.bare, "rev-parse", "main")
        with self.assertRaisesRegex(CheckpointHold, "PUBLICATION_CHECKPOINT_STALE_INPUT_HOLD"):
            push_checkpoint(self.work, pause=lambda _: None)
        self.assertEqual(self.git(self.bare, "rev-parse", "main"), before)

    def test_concurrent_distinct_commits_for_one_checkpoint_only_publish_once(self):
        self.commit(self.writer, "data/live.json", BASE_LIVE.replace("null", "10"),
                    "different worker's derived coverage")
        def publish(checkout):
            try:
                return push_checkpoint(checkout, pause=lambda _: None)
            except CheckpointHold as exc:
                return str(exc)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, (self.work, self.writer)))
        self.assertCountEqual(results, ["PUBLISHED", "PUBLICATION_CHECKPOINT_STALE_INPUT_HOLD"])
        self.assertEqual(self.git(self.bare, "rev-list", "--count", "main").strip(), b"2")

    def test_interrupt_before_push_restart_can_publish_once(self):
        original = subprocess.run
        def interrupted(args, **kwargs):
            if args[1] == "push":
                raise KeyboardInterrupt()
            return original(args, **kwargs)
        before = self.git(self.bare, "rev-parse", "main")
        with patch("push_publication_checkpoint.subprocess.run", side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                push_checkpoint(self.work, pause=lambda _: None)
        self.assertEqual(self.git(self.bare, "rev-parse", "main"), before)
        self.assertEqual(push_checkpoint(self.work, pause=lambda _: None), "PUBLISHED")
        self.assertEqual(push_checkpoint(self.work, pause=lambda _: None), "ALREADY_PUBLISHED")

    def test_v12_blind_rebase_can_mix_changed_live_with_stale_coverage(self):
        current = self.update_live()
        self.git(self.work, "fetch", "origin", "main")
        self.git(self.work, "rebase", "origin/main")
        self.assertEqual((self.work / "data/live.json").read_bytes(), current.replace(b"null", b"10"))

    def test_rejects_stale_preflight_and_preserves_the_remote_live(self):
        current = self.update_live()
        before = self.git(self.bare, "rev-parse", "main")
        with self.assertRaisesRegex(CheckpointHold, "PUBLICATION_CHECKPOINT_STALE_INPUT_HOLD"):
            push_checkpoint(self.work, pause=lambda _: None)
        self.assertEqual(self.git(self.bare, "rev-parse", "main"), before)
        self.assertEqual(self.git(self.bare, "show", "main:data/live.json"), current)

    def test_independent_change_can_be_rebased_then_the_checkpoint_publishes_once(self):
        self.commit(self.writer, "notes.txt", "independent", "separate file")
        self.git(self.writer, "push", "origin", "HEAD:refs/heads/main")
        self.git(self.work, "config", "user.name", "Isolated Test")
        self.git(self.work, "config", "user.email", "test@example.invalid")
        self.assertEqual(push_checkpoint(self.work, pause=lambda _: None), "PUBLISHED")
        once = self.git(self.bare, "rev-parse", "main")
        self.assertEqual(push_checkpoint(self.work, pause=lambda _: None), "ALREADY_PUBLISHED")
        self.assertEqual(self.git(self.bare, "rev-parse", "main"), once)
        self.assertEqual(self.git(self.bare, "show", "main:notes.txt"), b"independent")

    def test_lost_push_response_reconciles_the_exact_commit_without_duplication(self):
        original = subprocess.run
        hit = []

        def run(*args, **kwargs):
            response = original(*args, **kwargs)
            if args[0][1] == "push":
                hit.append(response.returncode)
                self.assertEqual(response.returncode, 0)
                raise subprocess.TimeoutExpired(args[0], 20)
            return response

        with patch("push_publication_checkpoint.subprocess.run", side_effect=run):
            self.assertEqual(push_checkpoint(self.work, pause=lambda _: None), "ALREADY_PUBLISHED")
        self.assertEqual(hit, [0])
        self.assertEqual(self.git(self.bare, "rev-list", "--count", "main").strip(), b"2")

    def test_successful_push_response_cannot_authorize_a_superseded_checkpoint(self):
        original = subprocess.run
        race_seen = []

        def run(args, **kwargs):
            result = original(args, **kwargs)
            if args[1] == "push" and kwargs.get("cwd") == self.work and result.returncode == 0:
                # An independent writer replaces Live before the first worker can dispatch.
                self.git(self.writer, "pull", "--ff-only", "origin", "main")
                race_seen.append(self.update_live())
            return result

        with patch("push_publication_checkpoint.subprocess.run", side_effect=run):
            with self.assertRaisesRegex(CheckpointHold, "PUBLICATION_CHECKPOINT_SUPERSEDED_HOLD"):
                push_checkpoint(self.work, pause=lambda _: None)
        self.assertEqual(len(race_seen), 1)
        self.assertEqual(self.git(self.bare, "show", "main:data/live.json"), race_seen[0])
        self.assertEqual(self.git(self.bare, "rev-list", "--count", "main").strip(), b"3")

    def test_previously_published_checkpoint_that_was_superseded_is_held(self):
        self.assertEqual(push_checkpoint(self.work, pause=lambda _: None), "PUBLISHED")
        self.git(self.writer, "pull", "--ff-only", "origin", "main")
        current = self.update_live()
        with self.assertRaisesRegex(CheckpointHold, "PUBLICATION_CHECKPOINT_SUPERSEDED_HOLD"):
            push_checkpoint(self.work, pause=lambda _: None)
        self.assertEqual(self.git(self.bare, "show", "main:data/live.json"), current)


if __name__ == "__main__":
    unittest.main()
