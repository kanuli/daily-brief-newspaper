"""Exercise the public snapshot release and notification with no network writes."""
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError
import sys
import unittest

import discord_public_live as discord
import live_public_snapshot as snapshot
import today_first_live as live
from test_editorial_authority_ci import CLOCK, CANDIDATE, SOURCE, TestKey, article, b64, claims, sign_claims


def read_files(files):
    def read(name):
        if name not in files:
            raise HTTPError(live.SITE+name, 404, "not found", None, None)
        return files[name]
    return read


def manifest(files, absent=None):
    return live.canonical(dict(schema=snapshot.SCHEMA, repository=live.REPO, reviewCommit=SOURCE,
        files={path: dict(size=len(value),sha256=snapshot.digest(value)) for path,value in files.items()},
        absent=[live.PAGES_RECEIPT] if absent is None else absent))


class LivePublicReleaseTests(unittest.TestCase):
    def setUp(self):
        self.base = {live.LIVE:b"old", "live.html":b"old html", "assets/static.js":b"old static"}

    def surveyed(self, raw, sha=None):
        return snapshot.reviewed(raw,sha_pin=sha or snapshot.digest(raw),commit=SOURCE,repo=live.REPO,
                                 receipt=live.PAGES_RECEIPT,required=(live.LIVE,"live.html"),parse=live.strict_json)

    def test_each_reviewed_file_is_reconstructed_and_drift_refuses_to_stage(self):
        plan = self.surveyed(manifest(self.base))
        with TemporaryDirectory() as root:
            target=Path(root)
            snapshot.checked_public(plan,read_files(self.base),output=target)
            self.assertEqual({p.relative_to(target).as_posix():p.read_bytes()
                              for p in target.rglob("*") if p.is_file()},self.base)
        updated=self.base | {"assets/static.js":b"replacement asset"}
        with self.assertRaisesRegex(ValueError,"bytes differ"):
            snapshot.checked_public(plan,read_files(updated))
        with self.assertRaisesRegex(ValueError,"path appeared"):
            snapshot.checked_public(plan,read_files(self.base | {live.PAGES_RECEIPT:b"new receipt"}))

    def test_wrong_pin_case_collisions_and_unsafe_paths_refused(self):
        with self.assertRaisesRegex(ValueError,"reviewed manifest pin"):
            self.surveyed(manifest(self.base),"f"*64)
        for name in ("assets/../escape.js","assets/%2e%2e/escape.js","assets/STATIC.js","assets/a?query=x"):
            with self.subTest(name=name),self.assertRaisesRegex(ValueError,"unsafe"):
                self.surveyed(manifest(self.base | {name:b"malformed"}))

    def test_bootstrap_claim_is_separately_scoped_bound_and_fresh(self):
        raw=article()
        base_hash=snapshot.digest(manifest(self.base))
        with TemporaryDirectory() as root:
            key=TestKey(Path(root),b"Y"*32)
            token=lambda **kw:b64(live.canonical(sign_claims(key,claims(raw,**kw))))
            kwargs=dict(scope=live.PUBLIC_BASE_SCOPE,publicBaselineSha256=base_hash)
            authorization=token(**kwargs)
            live.verify_approval(authorization,b64(key.public),raw,CANDIDATE,SOURCE,CLOCK,public_baseline=base_hash)
            with self.assertRaisesRegex(ValueError,"unrecognized"):
                live.verify_approval(token(),b64(key.public),raw,CANDIDATE,SOURCE,CLOCK,public_baseline=base_hash)
            with self.assertRaisesRegex(ValueError,"bind the public baseline"):
                live.verify_approval(authorization,b64(key.public),raw,CANDIDATE,SOURCE,CLOCK,public_baseline="d"*64)
            with self.assertRaisesRegex(ValueError,"expired"):
                live.verify_approval(authorization,b64(key.public),raw,CANDIDATE,SOURCE,CLOCK+timedelta(minutes=10),
                                     public_baseline=base_hash)

    def test_existing_v2_receipt_accepts_only_bounded_vocab_inventory(self):
        files={name:"b"*64 for name in live.RECEIPT_FILES}
        good=dict(schema="PUBLICATION_BUILD_RECEIPT_V2", sourceCommit=SOURCE,runId="70",runAttempt="1",
            files=files | {"data/vocab/latest.json":"b"*64,"data/vocab/2026-01-10.json":"c"*64})
        self.assertEqual(live.live_base_receipt(live.canonical(good),SOURCE),good)
        with self.assertRaisesRegex(ValueError,"unexpected tracked"):
            live.live_base_receipt(live.canonical(good | {"files":good["files"] | {"assets/test.js":"b"*64}}),SOURCE)

    def test_notice_uses_exact_public_payload_and_html(self):
        html=b"public HTML"
        version=b"new Live payload"
        receipt=live.canonical(dict(schema="PUBLICATION_BUILD_RECEIPT_V1",
                                   files={live.LIVE:snapshot.digest(version),"live.html":snapshot.digest(html)}))
        remote={live.PAGES_RECEIPT:receipt,live.LIVE:version,"live.html":html}
        self.assertEqual(discord.require_public_live(version,read=read_files(remote)),snapshot.digest(version))
        with self.assertRaisesRegex(ValueError,"does not match"):
            discord.require_public_live(b"repository-only",read=read_files(remote))
        with self.assertRaisesRegex(ValueError,"does not match"):
            discord.require_public_live(version,read=read_files(remote | {"live.html":b"outdated HTML"}))
        with self.assertRaises(HTTPError):
            discord.require_public_live(version,read=read_files({live.LIVE:version}))

    def test_actual_pages_run_owns_live_only_notices_even_when_repo_has_other_bytes(self):
        raw=article()
        html=b"published Live HTML"
        digest=snapshot.digest(raw)
        receipt=dict(schema="PUBLICATION_BUILD_RECEIPT_V1",runId="74",runAttempt="1",builderCommit=SOURCE,
                     liveCandidateCommit=CANDIDATE,liveDraftSha256=digest,
                     files={live.LIVE:digest,"live.html":snapshot.digest(html)})
        remote={live.PAGES_RECEIPT:live.canonical(receipt),live.LIVE:raw,"live.html":html}
        run=dict(id=74,run_attempt=1,head_sha=SOURCE,head_repository={"full_name":live.REPO},
                 head_branch="main",path=".github/workflows/pages.yml",conclusion="success")
        event=dict(action="completed",repository={"full_name":live.REPO},workflow_run=run)
        self.assertEqual(discord.published_live_for_run(event,read=read_files(remote))[1],digest)
        with self.assertRaisesRegex(ValueError,"not the exact completed"):
            discord.published_live_for_run(dict(event,workflow_run=dict(run,id=75)),read=read_files(remote))
        with self.assertRaisesRegex(ValueError,"provenance"):
            discord.published_live_for_run(dict(event,workflow_run=dict(run,head_branch="pending")),read=read_files(remote))



if __name__ == "__main__":
    unittest.main()
