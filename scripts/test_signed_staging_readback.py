"""Test event-specific Git effect proof and outage-safe signed staging."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from editorial_stage_authority import stage_once
from scheduled_publisher_handoff import stage_signed
from scheduled_publisher_preflight_receipt import CANDIDATE
from signed_live_publisher import git_blob
from staging_git_identity import LEGACY, paths_at, readback, stage_headline

BASE,TIP,ROOT,TREE,BLOB,LEGACY_BLOB=("a"*40, "b"*40, "c"*40,"d"*40,git_blob(b"draft"),"f"*40)
EVENT="1"*64
BINDING="2"*64
APP="approved-publisher[bot]"


class GitFixture:
    def __init__(self):
        self.current=BASE
        self.outage=False
        self.writes=0
        self.approvals=0
        self.commit={
            "sha":TIP,"parents":[{"sha":BASE}],"author":{"login":APP},
            "commit":{"message":stage_headline(EVENT),"verification":{"verified":True,"reason":"valid"}},
            "files":[{"filename":CANDIDATE,"sha":BLOB,"status":"added"}],
        }

    def api(self, name):
        if self.outage:
            raise TimeoutError("Git readback temporarily unavailable")
        return {
            "commits/"+TIP:self.commit,
            "git/commits/"+BASE:{"sha":BASE,"tree":{"sha":ROOT}},
            "git/commits/"+TIP:{"sha":TIP,"tree":{"sha":ROOT}},
            "git/trees/"+ROOT:{"sha":ROOT,"truncated":False,"tree":[
                {"path":"data","type":"tree","mode":"040000","sha":TREE}]},
            "git/trees/"+TREE:{"sha":TREE,"truncated":False,"tree":[
                {"path":LEGACY.removeprefix("data/"),"type":"blob","mode":"100644","sha":LEGACY_BLOB}]
                + ([{"path":CANDIDATE.removeprefix("data/"),"type":"blob","mode":"100644","sha":BLOB}]
                   if self.current==TIP else [])},
        }[name]

    def mutate(self,method,route,payload):
        self.writes+=1
        self.current=TIP
        self.last_request=payload["variables"]["input"]
        raise TimeoutError("Git accepted stage but response was lost")

    def authorize(self):
        self.approvals+=1

    def head(self,_branch):
        return self.current

    def prove(self):
        return readback(api=self.api,branch_head=self.head,parent=BASE,draft_blob=BLOB,event=EVENT,publisher=APP)


class StagingReadbackTests(unittest.TestCase):
    def setUp(self):
        self.git=GitFixture()

    def test_legacy_file_is_distinct_from_the_missing_formal_candidate(self):
        self.assertEqual(paths_at(self.git.api,BASE),{CANDIDATE:None,LEGACY:LEGACY_BLOB})

    def test_post_lost_response_is_recovered_once_with_event_and_app(self):
        git=self.git
        with patch("scheduled_publisher_handoff.gh",side_effect=git.mutate), \
                patch("scheduled_publisher_handoff.receipt.api",side_effect=git.api), \
                patch("scheduled_publisher_handoff.receipt.branch_head",side_effect=git.head):
            self.assertEqual(stage_signed(b"draft",BASE,BLOB,EVENT,APP,authorize=git.authorize),TIP)
        self.assertEqual(git.writes,1)
        self.assertEqual(git.approvals,1)
        self.assertEqual(git.last_request["expectedHeadOid"],BASE)
        self.assertEqual(git.last_request["message"]["headline"],stage_headline(EVENT))
        self.assertEqual([file["path"] for file in git.last_request["fileChanges"]["additions"]],[CANDIDATE])

    def test_journal_reopens_pending_and_recovers_read_only(self):
        git=self.git
        with TemporaryDirectory() as temp:
            directory=Path(temp)
            def lose():
                git.current=TIP
                git.writes+=1
                raise TimeoutError("lost after stage")
            with self.assertRaises(TimeoutError):
                stage_once(directory,EVENT,BINDING,lose)
            git.outage=True
            with self.assertRaises(TimeoutError):
                stage_once(directory,EVENT,BINDING,lambda:self.fail("second write"),git.prove)
            git.outage=False
            self.assertEqual(stage_once(directory,EVENT,BINDING,lambda:self.fail("second write"),git.prove),(TIP,False))
            self.assertEqual(stage_once(directory,EVENT,BINDING,lambda:self.fail("second write")),(TIP,False))
            self.assertEqual(git.writes,1)

    def test_wrong_author_forged_signature_event_or_parent_stays_hold(self):
        self.git.current=TIP
        from copy import deepcopy
        good=deepcopy(self.git.commit)
        for bad in (
            dict(good,author={"login":"another[bot]"}),
            dict(good,parents=[{"sha":"0"*40}]),
            dict(good,commit=dict(good["commit"],verification={"verified":False,"reason":"unsigned"})),
            dict(good,commit=dict(good["commit"],message=stage_headline("0"*64))),
        ):
            self.git.commit=bad
            with self.subTest(bad=bad), self.assertRaisesRegex(ValueError,"WRITER_OR_PARENT"):
                self.git.prove()

    def test_legitimate_app_cannot_attach_event_to_modified_content_or_extra_path(self):
        self.git.current=TIP
        good=list(self.git.commit["files"])
        for files in ([dict(good[0],sha=LEGACY_BLOB)],good+[dict(good[0],filename=LEGACY)]):
            self.git.commit["files"]=files
            with self.assertRaisesRegex(ValueError,"EXACT_BYTES"):
                self.git.prove()

    def test_mismatched_raw_bytes_are_rejected_before_network(self):
        with patch("scheduled_publisher_handoff.receipt.branch_head",side_effect=lambda *_:self.fail("contacted remote")):
            with self.assertRaisesRegex(ValueError,"bytes do not match"):
                stage_signed(b"changed",BASE,BLOB,EVENT,APP,authorize=self.git.authorize)

    def test_staged_grant_rechecks_expiry_immediately_before_submit(self):
        with patch("scheduled_publisher_handoff.gh",side_effect=lambda *_:self.fail("forbidden write")), \
                patch("scheduled_publisher_handoff.candidate_blob_at",return_value=None), \
                patch("scheduled_publisher_handoff.receipt.branch_head",return_value=BASE):
            def expired():
                raise ValueError("stage approval expired")
            with self.assertRaisesRegex(ValueError,"expired"):
                stage_signed(b"draft",BASE,BLOB,EVENT,APP,authorize=expired)

    def test_failed_preflight_does_not_consume_event_and_pending_never_runs_preflight_again(self):
        git = self.git
        with TemporaryDirectory() as temp:
            directory = Path(temp)
            def not_authorized():
                raise ValueError("staging app policy unverified")
            with self.assertRaisesRegex(ValueError,"policy unverified"):
                stage_once(directory,EVENT,BINDING,lambda:self.fail("forbidden write"),prepare=not_authorized)
            def lose():
                git.current = TIP
                git.writes += 1
                raise TimeoutError("lost after stage")
            with self.assertRaises(TimeoutError):
                stage_once(directory,EVENT,BINDING,lose,prepare=git.authorize)
            self.assertEqual(
                stage_once(directory,EVENT,BINDING,lambda:self.fail("second write"),git.prove,prepare=not_authorized),
                (TIP,False))
            self.assertEqual((git.writes,git.approvals),(1,1))



if __name__=="__main__":
    unittest.main()
