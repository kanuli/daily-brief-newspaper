"""Deterministic Live-only and authorization tests independent of working-site data."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest

from editorial_draft import draft_from_evidence
from editorial_stage_authority import ARTICLE_KEYS, BRANCH, CORE_SCOPE, EIC_SCOPE, TARGET, stage_once, verify
from verify_derived_live import validate as validate_projection
from scheduled_publication_contract import publisher_errors
from today_first_live import DESK_LABELS, HKT, REPO, SCOPE, candidate_live, canonical, verify_approval

# Reserved test identities and domains; nothing below is a deployment credential.
CLOCK = datetime(2026, 1, 10, 12, tzinfo=HKT)
URL = "https://news.example.org/articles/hong-kong-20260110"
OTHER = "https://news.example.org/articles/other"
DOC = "b"*64
CANDIDATE, SOURCE = "a"*40, "c"*40
COPY = dict(id="hong-kong-authority-ci-1", title="香港社區公共服務最新安排",
    dek="香港社區公共服務安排有新公布，資料供測試編採規則使用。",
    summary="香港社區服務安排更新，測試資料用來核對新聞正文與來源是否一致。",
    body="香港社區公共服務的安排在今日有新公布，服務時段及資料查詢渠道均列在原稿。這個測試固定文章時間及證據格式，方便比較發布程序的不同結果。\n\n市民可以按照已公布選項了解各區服務和下一步資訊。編採程序核對文章的原始來源、公眾通知時間以及適合的香港新聞分類，確認所有核實資料指向同一項發布。",
    context="各區公共服務按同一原稿公布資料，最新安排以原稿內的通知為準。",
    why="調整涉及不同社區的服務時段，因此有需要清楚交代通知的內容及時間。",
    watchNext="後續如有更新應按同一來源再核實，維持原有發布時間和編採紀錄。",
    status="NEW")
SOURCES = [dict(name="測試新聞原稿", url=URL, publishedAt=(CLOCK-timedelta(minutes=40)).isoformat(),
                verifiedAt=(CLOCK-timedelta(minutes=3)).isoformat(), documentSha256=DOC)]


def article(sources=None, primary=URL):
    sources = deepcopy(SOURCES if sources is None else sources)
    return draft_from_evidence(COPY,primary_url=primary,verified_sources=sources,
        evidence_sha256=sha256(canonical(sources)).hexdigest(),editorial_desk="hong-kong",
        now=CLOCK,labels=DESK_LABELS)


class TestKey:
    def __init__(self, root, seed):
        self.root=root
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        except ImportError:
            self.impl=None
        else:
            self.impl=Ed25519PrivateKey.from_private_bytes(seed)
            self.public=self.impl.public_key().public_bytes_raw()
            return
        self.path=root/("key-"+seed.hex())
        self.path.write_bytes(bytes.fromhex("302e020100300506032b657004220420")+seed)
        self.path.chmod(0o600)
        der=subprocess.check_output(["openssl","pkey","-inform","DER","-in",str(self.path),
                                     "-pubout","-outform","DER"],timeout=8)
        self.public=der[-32:]

    def sign(self, body):
        if self.impl is not None:
            return self.impl.sign(body)
        source=self.root/"message"
        source.write_bytes(body)
        return subprocess.check_output(["openssl","pkeyutl","-sign","-keyform","DER","-inkey",
                                        str(self.path),"-rawin","-in",str(source)],timeout=8)


def b64(raw):
    return base64.b64encode(raw).decode()


def claims(raw, **kw):
    result=dict(scope=SCOPE,repository=REPO,actor="CANTONESE_EIC",decision="APPROVE_LIVE_PAGES",
        candidateCommit=CANDIDATE,siteBaseCommit=SOURCE,draftSha256=sha256(raw).hexdigest(),
        issuedAt=CLOCK.isoformat(),expiresAt=(CLOCK+timedelta(minutes=10)).isoformat())
    result.update(kw)
    return result


def sign_claims(key,data):
    return dict(claims=data,signature=b64(key.sign(canonical(data))))


def signed_staging(raw,evidence,eic,core,*,time=CLOCK,**change):
    import json
    live=json.loads(raw)
    source={row["articleId"]:row for row in json.loads(evidence)}
    articles=[dict({k:item[k] for k in ARTICLE_KEYS},articleSha256=sha256(canonical(item)).hexdigest(),
                   documentSha256=source[item["id"]]["documentSha256"]) for item in live["items"]]
    data=dict(repository=REPO,branch=BRANCH,path=TARGET,prepublishParent=CANDIDATE,validatorCommit=SOURCE,
              draftSha256=sha256(raw).hexdigest(),evidenceSha256=sha256(evidence).hexdigest(),
              eventId="4"*64,issuedAt=time.isoformat(),expiresAt=(time+timedelta(minutes=9)).isoformat(),articles=articles)
    data.update(change)
    editorial=sign_claims(eic,dict(data,scope=EIC_SCOPE,actor="CANTONESE_EIC",decision="APPROVE_LIVE_STAGE"))
    authorized=sign_claims(core,dict(data,scope=CORE_SCOPE,actor="CENTRAL_CORE",decision="AUTHORIZE_LIVE_STAGE",
                             eicReceiptSha256=sha256(canonical(editorial)).hexdigest()))
    return canonical(dict(eic=editorial,core=authorized))


class CandidateCodeSecurity(unittest.TestCase):
    def test_valid_single_article_independent_of_neighbouring_publications(self):
        raw=article()
        valid=candidate_live(raw,now=CLOCK)
        self.assertEqual(len(valid["items"]),1)
        self.assertEqual(valid["items"][0]["sourceUrl"],URL)
        self.assertEqual(valid["items"][0]["sourceName"],SOURCES[0]["name"])
        self.assertEqual(publisher_errors(valid,now=CLOCK),[])

    def test_invalid_route_and_evidence_are_rejected(self):
        for patch, expected in ((dict(deskSlugs=["hong-kong","japan"]),"editorial route"),
                                (dict(sourceName="錯誤名稱"),"primary source")):
            with self.subTest(patch=patch):
                import json
                obj=json.loads(article())
                obj["items"][0].update(patch)
                with self.assertRaisesRegex(ValueError,expected):
                    candidate_live(canonical(obj),now=CLOCK)
        with self.assertRaisesRegex(ValueError,"primary source not linked"):
            article(primary=OTHER)

    def test_claims_exact_bytes_role_key_scope_and_expiry(self):
        with TemporaryDirectory() as d:
            key=TestKey(Path(d),b"A"*32)
            other=TestKey(Path(d),b"B"*32)
            raw=article()
            good=claims(raw)
            token=lambda c,k=key:b64(canonical(dict(claims=c,signature=b64(k.sign(canonical(c))))))
            verify_approval(token(good),b64(key.public),raw,CANDIDATE,SOURCE,CLOCK)
            for cap, signer, body, commit, site, now, error in (
              (good,other,raw,CANDIDATE,SOURCE,CLOCK,"invalid Core"),
              (good,key,raw+b"\n",CANDIDATE,SOURCE,CLOCK,"does not bind"),
              (good,key,raw,"d"*40,SOURCE,CLOCK,"does not bind"),
              (good,key,raw,CANDIDATE,"d"*40,CLOCK,"does not bind"),
              (good,key,raw,CANDIDATE,SOURCE,CLOCK+timedelta(minutes=10),"expired"),
              (claims(raw,actor="CTO"),key,raw,CANDIDATE,SOURCE,CLOCK,"wrong approval")):
                with self.subTest(error=error), self.assertRaisesRegex(ValueError,error):
                    verify_approval(token(cap,signer),b64(key.public),body,commit,site,now)

    def test_candidate_cannot_claim_full_publication_coverage(self):
        import json
        candidate=json.loads(article())
        candidate["coverage"]={"status":"COMPLETE"}
        with self.assertRaisesRegex(ValueError,"must not assert"):
            candidate_live(canonical(candidate),now=CLOCK)


    def test_dual_signed_stage_scopes_authorized_source_and_single_git_write(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            eic,core=(TestKey(root,label*32) for label in (b"E",b"C"))
            pins=dict(eic=b64(eic.public),core=b64(core.public))
            raw=article()
            evidence=canonical([dict(SOURCES[0],articleId=COPY["id"])])
            packet=signed_staging(raw,evidence,eic,core)
            check=lambda p,doc=evidence,when=CLOCK:verify(raw,p,doc,pins=pins,parent=CANDIDATE,validator=SOURCE,now=when)
            event,binding=check(packet)
            written=[]
            def publish():
                written.append("exact authorized bytes")
                return "f"*40
            self.assertEqual(stage_once(root,event,binding,publish),("f"*40,True))
            self.assertEqual(stage_once(root,event,binding,publish),("f"*40,False))
            self.assertEqual(len(written),1)
            with self.assertRaisesRegex(ValueError,"reused"):
                stage_once(root,event,"2"*64,publish)
            with self.assertRaisesRegex(ValueError,"exact payload"):
                check(signed_staging(raw,evidence,eic,core,path="data/live.json"))
            with self.assertRaisesRegex(ValueError,"invalid Core"):
                check(signed_staging(raw,evidence,core,core))
            with self.assertRaisesRegex(ValueError,"expired"):
                check(packet,when=CLOCK+timedelta(minutes=9))
            damaged=canonical([dict(SOURCES[0],articleId=COPY["id"],name="未核實來源")])
            with self.assertRaisesRegex(ValueError,"evidence disagree"):
                check(signed_staging(raw,damaged,eic,core),damaged)

    def test_lost_response_reservation_survives_reopen_without_second_write(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            def remote():
                raise TimeoutError("lost response after synthetic Git commit")
            with self.assertRaises(TimeoutError):
                stage_once(root,"3"*64,"6"*64,remote)
            with self.assertRaisesRegex(ValueError,"outcome unknown"):
                stage_once(root,"3"*64,"6"*64,lambda:self.fail("duplicate write"))

    def test_automatic_writers_can_only_change_coverage(self):
        import json
        prior=json.loads(article())
        projected=dict(prior,coverage={"status":"INCOMPLETE"})
        validate_projection(prior,projected)
        for changed in (dict(prior,date="2026-01-09"),dict(prior,items=[]),
                        {k:v for k,v in prior.items() if k!="publicationContract"}):
            with self.assertRaisesRegex(ValueError,"only derived coverage"):
                validate_projection(prior,changed)
        validate_projection({"mode":"legacy"},{"mode":"legacy","coverage":{}})
        with self.assertRaisesRegex(ValueError,"LIVE_WRITE_AUTHORITY_HOLD"):
            validate_projection({"mode":"legacy"},{"mode":"legacy","items":[]})


if __name__=="__main__":
    unittest.main()
