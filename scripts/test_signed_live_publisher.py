"""Exercise the exact release adapter with an isolated GitHub transport contract."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import json
import unittest

from editorial_stage_authority import ARTICLE_KEYS, digest
from signed_live_publisher import CORE_SCOPE,EIC_SCOPE,git_blob,headline,publish_once
from test_editorial_authority_ci import CLOCK,COPY,SOURCES,TestKey,article,b64,sign_claims
from today_first_live import LIVE,REPO,canonical

BASE="a"*40
STAGED="b"*40
RESULT="c"*40
PUBLISHER="publisher-dev[bot]"
CUSTODY="1"*64
EVENT="2"*64


def make_release(raw,evidence,key,core,*,parent=BASE,staged=STAGED,publisher=PUBLISHER,
                 custody=CUSTODY,event=EVENT,when=CLOCK,patch=None):
    source={r["articleId"]:r for r in json.loads(evidence)}
    items=json.loads(raw)["items"]
    fields=dict(repository=REPO,branch="main",path=LIVE,mainParent=parent,stagedCommit=staged,
        publisher=publisher,draftSha256=digest(raw),evidenceSha256=digest(evidence),
        coreCustodySha256=custody,eventId=event,issuedAt=when.isoformat(),
        expiresAt=(when+timedelta(minutes=6)).isoformat(),
        articles=[dict({k:i[k] for k in ARTICLE_KEYS},articleSha256=digest(canonical(i)),
                       documentSha256=source[i["id"]]["documentSha256"]) for i in items])
    fields.update(patch or {})
    eic=sign_claims(key,dict(fields,scope=EIC_SCOPE,actor="CANTONESE_EIC",decision="APPROVE_LIVE_WRITE"))
    grant=sign_claims(core,dict(fields,scope=CORE_SCOPE,actor="CENTRAL_CORE",decision="AUTHORIZE_LIVE_WRITE",
                               eicReceiptSha256=digest(canonical(eic))))
    return canonical(dict(eic=eic,core=grant))


class LocalGitHub:
    def __init__(self,raw):
        self.main=BASE
        self.staged=STAGED
        self.blob=git_blob(raw)
        self.raw=raw
        self.calls=0
        self.lost=False
        self.outage=False
        self.callback=lambda:None
        self.commit=None

    def branch(self,name):
        return self.main if name=="main" else self.staged

    def api(self,path):
        if self.outage:
            raise TimeoutError("readback unavailable")
        assert path=="commits/"+RESULT
        return self.commit

    def write(self,packet):
        self.calls+=1
        self.callback()
        req=packet["variables"]["input"]
        assert req["branch"]=={"repositoryNameWithOwner":REPO,"branchName":"main"}
        assert req["expectedHeadOid"]==self.main==BASE
        assert req["fileChanges"]=={"additions":[dict(path=LIVE,contents=base64.b64encode(self.raw).decode())]}
        assert req["message"]["headline"]==headline(dict(eventId=EVENT))
        self.commit=dict(sha=RESULT,parents=[{"sha":BASE}],author={"login":PUBLISHER},
                         commit={"message":req["message"]["headline"]},
                         files=[dict(filename=LIVE,sha=self.blob)])
        self.main=RESULT
        if self.lost:
            raise TimeoutError("write response lost")
        return RESULT


class ReleaseBoundary(unittest.TestCase):
    def setUp(self):
        tmp=TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir=Path(tmp.name)
        self.eic,self.core,self.wrong=(TestKey(self.dir,k*32) for k in (b"E",b"C",b"W"))
        self.raw=article()
        self.evidence=canonical([dict(SOURCES[0],articleId=COPY["id"])])
        self.remote=LocalGitHub(self.raw)
        self.envelope=make_release(self.raw,self.evidence,self.eic,self.core)
        self.moment=CLOCK

    def invoke(self, *, envelope=None,evidence=None,raw=None,preflight=lambda:None):
        return publish_once(raw or self.raw,envelope or self.envelope,evidence or self.evidence,
                            pins=dict(eic=b64(self.eic.public),core=b64(self.core.public)),
                            parent=BASE,staged=STAGED,publisher=PUBLISHER,directory=self.dir,
                            clock=lambda:self.moment,branch_head=self.remote.branch,api=self.remote.api,
                            staged_blob=lambda _:self.remote.blob,mutation=self.remote.write,check_mutation_ready=preflight)

    def test_exact_signed_effect_and_replay_no_duplicate(self):
        r=self.invoke()
        self.assertEqual((r["commit"],r["liveBlob"],r["coreCustodySha256"]),(RESULT,self.remote.blob,CUSTODY))
        self.assertEqual(r["status"],"RECORDED")
        self.assertEqual(self.invoke()["status"],"ALREADY_RECORDED")
        self.assertEqual(self.remote.calls,1)

    def test_lost_response_recovers_across_reopen_with_readback_only(self):
        self.remote.lost=True
        self.remote.outage=True
        with self.assertRaises(TimeoutError):
            self.invoke()
        self.remote.outage=False
        r=self.invoke()
        self.assertEqual((r["commit"],r["status"]),(RESULT,"RECONCILED"))
        self.assertEqual(self.remote.calls,1)

    def test_expired_after_commit_recovers_read_only_without_second_mutation(self):
        self.remote.lost=True
        self.remote.outage=True
        with self.assertRaises(TimeoutError):
            self.invoke()
        self.remote.outage=False
        self.moment+=timedelta(minutes=7)
        def unexpected_write():
            self.fail("expired recovery must not pass through the live mutation boundary")
        self.remote.callback=unexpected_write
        r=self.invoke(preflight=unexpected_write)
        self.assertEqual((r["commit"],r["status"],r["coreCustodySha256"]),(RESULT,"RECONCILED",CUSTODY))
        self.assertEqual(self.remote.calls,1)

    def test_expired_reserved_request_with_no_remote_effect_remains_held(self):
        def lost_before_accepting():
            raise TimeoutError("write transport failed before acceptance")
        self.remote.callback=lost_before_accepting
        with self.assertRaisesRegex(ValueError,"OUTCOME_UNKNOWN"):
            self.invoke()
        self.moment+=timedelta(minutes=7)
        with self.assertRaisesRegex(ValueError,"OUTCOME_UNKNOWN"):
            self.invoke()
        self.assertEqual(self.remote.calls,1)

    def test_retained_event_rejects_forged_approval_even_when_expired(self):
        self.invoke()
        self.moment+=timedelta(minutes=7)
        forged=make_release(self.raw,self.evidence,self.wrong,self.core)
        with self.assertRaisesRegex(ValueError,"invalid Core approval"):
            self.invoke(envelope=forged)
        self.assertEqual(self.remote.calls,1)

    def test_forged_or_unauthorized_publisher_and_expired_cannot_send(self):
        for variant,msg in (
            (make_release(self.raw,self.evidence,self.wrong,self.core),"invalid Core approval"),
            (make_release(self.raw,self.evidence,self.eic,self.core,publisher="other"),"predecessor, or destination"),
            (make_release(self.raw,self.evidence,self.eic,self.core,patch={"path":"data/other.json"}),"predecessor, or destination")):
            with self.subTest(msg=msg),self.assertRaisesRegex(ValueError,msg): self.invoke(envelope=variant)
        with self.assertRaisesRegex(ValueError,"incorrect actor"):
            self.invoke(preflight=lambda:(_ for _ in ()).throw(ValueError("incorrect actor")))
        self.moment+=timedelta(minutes=7)
        with self.assertRaisesRegex(ValueError,"expired"):
            self.invoke()
        self.assertEqual(self.remote.calls,0)

    def test_wrong_source_and_staging_change_are_rejected(self):
        invalid=canonical([dict(SOURCES[0],articleId=COPY["id"],name="錯誤來源")])
        with self.assertRaisesRegex(ValueError,"source and evidence disagree"):
            self.invoke(evidence=invalid,envelope=make_release(self.raw,invalid,self.eic,self.core))
        self.remote.staged="d"*40
        with self.assertRaisesRegex(ValueError,"staged bytes changed"):
            self.invoke()
        self.assertEqual(self.remote.calls,0)

    def test_competing_request_sees_reservation_while_first_write_is_in_flight(self):
        started, proceed=Event(),Event()
        def delay():
            started.set()
            self.assertTrue(proceed.wait(5),"test writer timeout")
        self.remote.callback=delay
        with ThreadPoolExecutor(max_workers=1) as actor:
            first=actor.submit(self.invoke)
            try:
                self.assertTrue(started.wait(5))
                with self.assertRaisesRegex(ValueError,"OUTCOME_UNKNOWN"):
                    self.invoke()
            finally:
                proceed.set()
            self.assertEqual(first.result(timeout=5)["commit"],RESULT)
        self.assertEqual(self.remote.calls,1)


if __name__=="__main__": unittest.main()
