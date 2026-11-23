"""A checkpoint may update derived coverage, never write Live editorial data."""
from pathlib import Path
from types import SimpleNamespace
import json
import unittest
from unittest.mock import patch

from push_publication_checkpoint import CheckpointHold, push_checkpoint
from verify_derived_live import validate, validate_bytes

BASE="a"*40
TIP="b"*40
LIVE="data/live.json"


def raw(value):
    return json.dumps(value).encode()


class FakeGit:
    def __init__(self, after, *, paths=(LIVE,), parent_line=f"{TIP} {BASE}"):
        self.before={"mode":"live","items":[{"id":"first"}]}
        self.after=after
        self.paths=paths
        self.parent_line=parent_line
        self.pushed=False
        self.calls=[]

    def __call__(self,args,**kw):
        command=tuple(args[1:])
        self.calls.append(command)
        code=0
        output=b""
        if command==("rev-parse","HEAD"):
            output=TIP.encode()
        elif command==("rev-list","--parents","-n","1",TIP):
            output=self.parent_line.encode()
        elif command==("rev-parse","HEAD^"):
            output=BASE.encode()
        elif command==("rev-parse","FETCH_HEAD"):
            output=(TIP if self.pushed else BASE).encode()
        elif command[0]=="show" and command[1]==BASE+":"+LIVE:
            output=raw(self.before)
        elif command[0]=="show" and command[1]==TIP+":"+LIVE:
            output=raw(self.after)
        elif command[:3]==("diff","--no-renames","--name-only"):
            output=b"\0".join(p.encode() for p in self.paths)+b"\0"
        elif command[0]=="merge-base":
            code=int(command[2]==TIP and not self.pushed)
        elif command[0]=="push":
            self.pushed=True
        return SimpleNamespace(returncode=code,stdout=output,check_returncode=lambda:None)


class CheckpointBoundary(unittest.TestCase):
    def test_legacy_editorial_replacement_is_stopped(self):
        with self.assertRaisesRegex(ValueError,"LIVE_WRITE_AUTHORITY_HOLD"):
            validate({"mode":"live","items":[{"id":"first"}]},{"mode":"live","items":[{"id":"second"}]})

    def test_json_boolean_cannot_replace_integer_editorial_data(self):
        with self.assertRaisesRegex(ValueError,"LIVE_WRITE_AUTHORITY_HOLD"):
            validate_bytes(b'{"newCount":1}',b'{"newCount":true,"coverage":{}}')

    def test_duplicate_keys_and_non_objects_cannot_pass(self):
        for corrupt in (b'{"items":[],"items":[]}', b'[]', b'null'):
            with self.subTest(corrupt=corrupt),self.assertRaises(ValueError):
                validate_bytes(b'{"items":[]}',corrupt)

    def test_unsigned_article_write_does_not_reach_git_push(self):
        fake=FakeGit({"mode":"live","items":[{"id":"substitute"}]})
        with patch("push_publication_checkpoint.subprocess.run", side_effect=fake):
            with self.assertRaisesRegex(CheckpointHold,"LIVE_WRITE_AUTHORITY_HOLD"):
                push_checkpoint(".")
        self.assertFalse(fake.pushed)

    def test_coverage_and_non_live_updates_use_exact_validated_commit(self):
        for paths in [(LIVE,),("data/stocks-latest.json",)]:
            fake=FakeGit({"mode":"live","items":[{"id":"first"}],"coverage":{"good":True}},paths=paths)
            with patch("push_publication_checkpoint.subprocess.run", side_effect=fake):
                self.assertEqual(push_checkpoint("."),"PUBLISHED")
            self.assertIn(("push","origin",TIP+":refs/heads/main"),fake.calls)

    def test_case_alias_or_merge_cannot_bypass_single_commit_verification(self):
        for fake in (FakeGit({},paths=("Data/Live.json",)),FakeGit({},parent_line=f"{TIP} {BASE} {'c'*40}")):
            with patch("push_publication_checkpoint.subprocess.run",side_effect=fake):
                with self.assertRaises(CheckpointHold):
                    push_checkpoint(".")
            self.assertFalse(fake.pushed)

    def test_maintenance_legacy_failover_is_hold_and_coverage_uses_checked_commit(self):
        path=Path(__file__).resolve().parents[1]/".github/workflows/live-publication-maintenance.yml"
        workflow=path.read_text(encoding="utf-8")
        fallback=workflow.split("      - name: Hold legacy failover pending the signed Publisher",1)[1]
        fallback=fallback.split("      - name:",1)[0]
        self.assertIn("LIVE_FAILOVER_REQUIRES_EIC_CORE_SIGNED_PUBLISHER",fallback)
        self.assertIn("exit 1",fallback)
        self.assertNotIn("git push",workflow)
        self.assertIn("if python -B scripts/push_publication_checkpoint.py",workflow)


if __name__=="__main__":
    unittest.main()
