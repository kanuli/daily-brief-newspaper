"""Exact contract and single-use CAS checks, with no production Git transport."""
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from scoped_data_gateway import REPO, SCOPE, commit_once, prepare
from test_editorial_authority_ci import CLOCK, TestKey, b64, sign_claims
from today_first_live import canonical

BASE="a"*40
RESULT="b"*40
STOCK="stock-publication-maintenance.yml"
VOCAB="daily-japanese-vocab.yml"
DAILY="daily-today-recovery.yml"


class GatewayTests(unittest.TestCase):
    def setUp(self):
        root=Path(self.enterContext(TemporaryDirectory()))
        self.core=TestKey(root,b"g"*32)
        self.wrong=TestKey(root,b"x"*32)
        self.files={"data/stocks-latest.json":b'{"run":"dev"}'}
        self.head=BASE
        self.calls=[]
        self.now=CLOCK

    def grant(self, files, *, changes=None, key=None, workflow=STOCK):
        body=dict(scope=SCOPE,issuer="CENTRAL_CORE",repository=REPO,branch="main",workflow=workflow,
                  expectedHead=BASE,eventId="f"*64,issuedAt=CLOCK.isoformat(),
                  expiresAt=(CLOCK+timedelta(minutes=3)).isoformat(),
                  files=[dict(path=k,sha256=sha256(v).hexdigest()) for k,v in sorted(files.items())])
        body.update(changes or {})
        return canonical(sign_claims(key or self.core,body))

    def submit(self,packet,*,files=None,workflow=STOCK,transport=None):
        def mutate(request):
            self.calls.append(request)
            self.assertEqual(request["variables"]["input"]["expectedHeadOid"],self.head)
            self.head=RESULT
            return RESULT
        return commit_once(packet,files=files or self.files,workflow_identity=workflow,core_key=b64(self.core.public),
                           expected_head=BASE,clock=lambda:self.now,read_head=lambda:self.head,git_cas=transport or mutate)

    def test_stock_once_and_wrong_predecessor(self):
        grant=self.grant(self.files)
        self.assertEqual(self.submit(grant),RESULT)
        with self.assertRaisesRegex(ValueError,"predecessor moved"):
            self.submit(grant)
        self.assertEqual(len(self.calls),1)

    def test_daily_and_vocabulary_have_preserved_exact_route(self):
        for workflow,files in [(DAILY,{"data/latest.json":b"daily"}),(VOCAB,{"data/vocab/2026-11-23.json":b"lex"})]:
            packet=prepare(self.grant(files,workflow=workflow),files=files,workflow_identity=workflow,
                           core_key=b64(self.core.public),expected_head=BASE,now=self.now)
            self.assertEqual([v["path"] for v in packet["variables"]["input"]["fileChanges"]["additions"]],list(files))

    def test_forged_wrong_role_and_expired_grants_are_denied(self):
        for grant in (self.grant(self.files,key=self.wrong),self.grant(self.files,changes={"workflow":VOCAB}),
                      self.grant(self.files,changes={"expectedHead":"c"*40})):
            with self.assertRaises(ValueError):
                self.submit(grant)
        self.now+=timedelta(minutes=4)
        with self.assertRaisesRegex(ValueError,"expired"):
            self.submit(self.grant(self.files))
        self.assertFalse(self.calls)

    def test_core_signed_live_mixed_paths_and_substituted_data_denied(self):
        mixed=self.files | {"data/live.json":b"malformed"}
        with self.assertRaisesRegex(ValueError,"outside"):
            self.submit(self.grant(mixed),files=mixed)
        with self.assertRaisesRegex(ValueError,"exact file bytes"):
            self.submit(self.grant(self.files),files={"data/stocks-latest.json":b"substituted"})
        self.assertFalse(self.calls)

    def test_ambiguous_remote_result_cannot_duplicate_when_actual_head_advanced(self):
        def lost(request):
            self.head=RESULT
            self.calls.append(request)
            raise TimeoutError("reply lost after CAS")
        token=self.grant(self.files)
        with self.assertRaises(TimeoutError):
            self.submit(token,transport=lost)
        with self.assertRaisesRegex(ValueError,"predecessor moved"):
            self.submit(token,transport=lost)
        self.assertEqual(len(self.calls),1)


if __name__ == "__main__":
    unittest.main()
