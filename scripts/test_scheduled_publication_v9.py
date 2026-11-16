import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest.mock import patch

import build_today_daily_from_desk as daily
import catch_up_live_into_desk as catchup
from desk_freshness_policy import HKT
from merge_live_into_desk import FLOORS, DESK_LABELS, merge
from scheduled_publication_contract import CONTRACT, desk_checkpoint_errors, publisher_errors, time_label

ROOT = Path(__file__).resolve().parents[1]
ACTUAL = ROOT.parent / "evidence/live_52a32dc.json"


def story(slug, index, when):
    routes = [slug, "football"] if slug == "manchester-united" else [slug]
    text = "這是測試資料，只用來驗證編審欄位和排版規則，確認流程在不同新聞分類會維持一致的處理方式。"
    timestamp = when.isoformat()
    return dict(id=f"publisher-test-{slug}-{index}", title=f"測試-{slug}-{index}", desk=slug, deskSlugs=routes,
                section=DESK_LABELS[slug], sectionLabel=DESK_LABELS[slug],
                dek=text, summary=text, body=text*2+"\n\n"+text*2, context=text, why=text, watchNext=text,
                sourceName="Fixture", sourceUrl="https://example.invalid/test-story",
                sources=[{"name":"Fixture", "url":"https://example.invalid/test-story"}],
                publishedAt=timestamp, verifiedAt=timestamp, timeLabel=time_label(timestamp), status="NEW")


def fixture():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    when = now - timedelta(seconds=5)
    stamp = when.isoformat()
    date = when.astimezone(HKT).date().isoformat()
    items = [story(slug, 0, when) for slug in FLOORS]
    rows = {slug: [story(slug, n+1, when) for n in range(floor)] for slug, floor in FLOORS.items()}
    live = dict(publicationContract=CONTRACT, mode="live", date=date, lastUpdated=stamp,
                lastUpdatedLabel="fixture", windowLabel="fixture", nextUpdateLabel="fixture",
                newCount=len(items), updatedCount=0, developingCount=0, items=items,leadId=items[0]["id"])
    desk = dict(mode="ROLLING_DESK_LATEST", desks=rows, date=date, generatedAt=(when-timedelta(minutes=20)).isoformat())
    return live,desk


def pages_block(workflow):
    part = workflow.read_text(encoding="utf-8").split("Availability gate — JSON readable and publication state complete",1)[1]
    return compile(textwrap.dedent(part.split("python - <<'PY'\n",1)[1].split("\n          PY",1)[0]), str(workflow), "exec")


class PublicationTests(unittest.TestCase):
    def test_actual_commit_is_held_without_backfilling_labels(self):
        live = json.loads(ACTUAL.read_bytes())
        errors = publisher_errors(live)
        self.assertEqual(sum("missing timeLabel" in x for x in errors),9)
        self.assertEqual(sum("invalid editorial route" in x for x in errors),3)
        self.assertNotIn("coverage",live)
        with self.assertRaisesRegex(SystemExit,"missing timeLabel"):
            merge(live,fixture()[1])

    def test_workflow_preflight_holds_exact_current_github_blob_before_writes(self):
        recorded = ROOT.parent / "evidence/live_cfb1ad1.json"
        commit = "cfb1ad1e89d7037d31f0cacae42bf87a9c28a190"
        raw = recorded.read_bytes()
        proc = subprocess.run([sys.executable, "-B", "scripts/scheduled_publication_contract.py",
                               str(recorded), "--merge-commit", commit],
                              cwd=ROOT, capture_output=True, timeout=15)
        self.assertEqual(proc.returncode, 1, proc.stderr)
        receipt = json.loads(proc.stdout)
        self.assertEqual(receipt["status"], "HOLD")
        self.assertEqual(receipt["sourceCommit"], commit)
        self.assertEqual(receipt["liveSha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(sum("missing timeLabel" in e for e in receipt["errors"]), 9)
        self.assertEqual(recorded.read_bytes(), raw)
        workflow = (ROOT / ".github/workflows/merge-live-into-desk.yml").read_text(encoding="utf-8")
        self.assertLess(workflow.index("--merge-commit"), workflow.index("Normalize and validate Daily"))
        self.assertLess(workflow.index("--merge-commit"), workflow.index("scripts/push_publication_checkpoint.py"))
        self.assertEqual(workflow.count("python scripts/push_publication_checkpoint.py"), 3)
        self.assertLess(workflow.index("Recover hard desk depth"), workflow.index("Merge current Live and derive coverage"))

    def test_contract_checkpoint_does_not_require_daily_until_pages(self):
        from scheduled_publication_contract import merge_preflight
        from validate_publication_current import validate_live

        live, desk = fixture()
        raw = json.dumps(live, ensure_ascii=False).encode("utf-8")
        self.assertEqual(merge_preflight(raw, "a"*40)["status"], "PASS")
        malformed = merge_preflight(b"{", "a"*40)
        self.assertEqual(malformed["status"], "HOLD")
        self.assertEqual(malformed["liveSha256"], hashlib.sha256(b"{").hexdigest())
        published, merged = merge(live, desk)
        self.assertEqual(merge_preflight(json.dumps(published).encode(), "b"*40)["status"], "PASS")
        validate_live({}, published, merged, rolling_desk_checkpoint=True)
        with self.assertRaisesRegex(SystemExit, "independently current Daily"):
            validate_live({"date": "2026-10-13"}, published, merged)
        validate_live({"date": published["date"]}, published, merged)
        published["coverage"]["deskLatestStoryCounts"]["world"] += 1
        with self.assertRaisesRegex(SystemExit, "count, depth or identity mismatch"):
            validate_live({}, published, merged, rolling_desk_checkpoint=True)

    def test_source_backed_historical_live_progresses_without_retimestamping_articles(self):
        from scheduled_publication_contract import merge_preflight
        from validate_publication_current import validate_live

        historical = ROOT.parent / "evidence"
        live = json.loads((historical / "public_live_20261013.json").read_bytes())
        desk = json.loads((historical / "public_desk_20261013.json").read_bytes())
        now = datetime.fromisoformat(live["lastUpdated"])
        items = copy.deepcopy(live["items"])
        # Stage the captured articles as a Publisher payload. The source
        # archive, original timestamps, article text and routing remain intact.
        live["publicationContract"] = CONTRACT
        live.pop("coverage")
        raw = json.dumps(live, ensure_ascii=False).encode("utf-8")
        self.assertEqual(merge_preflight(raw, "a"*40, now=now)["status"], "PASS")
        accepted, merged = merge(live, desk, now=now)
        self.assertEqual(accepted["items"], items)
        self.assertEqual(accepted["lastUpdated"], live["lastUpdated"])
        self.assertEqual(accepted["coverage"]["status"], "COMPLETE")
        validate_live({}, accepted, merged, rolling_desk_checkpoint=True, now=now)

        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp)
            for name, value in [("latest", {}), ("live", accepted), ("desk-latest", merged)]:
                (data / f"{name}.json").write_text(json.dumps(value), encoding="utf-8")
            with patch.object(daily, "DATA", data):
                edition, result = daily.build(now=now)
        self.assertTrue(result["changed"])
        self.assertGreaterEqual(len(edition["articles"]), 8)
        self.assertEqual(edition["date"], live["date"])
        validate_live(edition, accepted, merged, now=now)

    def test_source_timestamp_and_label_validation(self):
        live,_ = fixture()
        for key,value,reason in [
            ("verifiedAt", "2026-11-15T00:00", "invalid source or verification timestamp"),
            ("publishedAt","2040-01-01T00:00:00Z","timestamps out of order"),
            ("sourceUrl","https://example.invalid", "missing direct source evidence"),
            ("timeLabel","01月01日 00:00 HKT核實","timeLabel does not match"),
            ("publishedAt","2020-01-01T00:00:00Z","older than"),
        ]:
            candidate = copy.deepcopy(live)
            candidate["items"][0][key] = value
            self.assertIn(reason, publisher_errors(candidate)[0])
        self.assertEqual(publisher_errors(live), [])

    def test_coverage_recomputed_from_actual_merged_desk_and_identity(self):
        live,desk=fixture()
        live["coverage"]={"status":"COMPLETE","publishingGateMet":True,"deskLatestStoryCounts":{"world":233}}
        current,merged=merge(live,desk)
        self.assertEqual(desk_checkpoint_errors(current,merged),[])
        self.assertEqual(current["coverage"]["deskLatestStoryCounts"]["world"],len(merged["desks"]["world"]))
        invalid=copy.deepcopy(current)
        invalid["coverage"]["deskLatestStoryCounts"]["world"]+=1
        self.assertIn("world",desk_checkpoint_errors(invalid,merged)[0])
        changed=copy.deepcopy(merged)
        next(row for row in changed["desks"]["world"] if row["id"]==current["leadId"])["body"]="different"
        self.assertIn("accepted article",desk_checkpoint_errors(current,changed)[0])

    def test_historical_rejection_skips_to_valid_current_without_rewriting_live(self):
        live,desk=fixture()
        old=copy.deepcopy(live)
        anchor=datetime.fromisoformat(live["lastUpdated"])
        old["lastUpdated"]=(anchor-timedelta(minutes=3)).isoformat()
        for item in old["items"]:
            item["publishedAt"] = item["verifiedAt"] = old["lastUpdated"]
            item["timeLabel"] = time_label(item["verifiedAt"])
        old["items"][0].pop("timeLabel")
        # One bad historical article plus eight valid-looking siblings used to
        # cause a failed merge to escape catch-up instead of quarantining it.
        with tempfile.TemporaryDirectory() as tmp:
            lp,dp=(Path(tmp)/x for x in ("live.json","desk-latest.json"))
            raw=json.dumps(live).encode();lp.write_bytes(raw);dp.write_text(json.dumps(desk))
            with patch.multiple(catchup,LIVE=lp,DESK=dp), patch.object(catchup,"git_output",return_value="a"*40), patch.object(catchup,"committed_live",return_value=old):
                self.assertEqual(catchup.main(),0)
                after=dp.read_bytes()
                self.assertEqual(catchup.main(),0)
                self.assertEqual(dp.read_bytes(),after)
            self.assertEqual(lp.read_bytes(),raw)
            self.assertEqual(json.loads(after)["generatedAt"],live["lastUpdated"])

    def test_pages_gate_original_missing_counts_and_candidate_success(self):
        live,desk=fixture()
        merged_live,merged_desk=merge(live,desk)
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/"data";data.mkdir()
            cwd=Path.cwd()
            try:
                os.chdir(tmp)
                for name,content in [("latest.json",{"date":live["date"]}),("stocks-latest.json",{}),
                                     ("live.json",live),("desk-latest.json",merged_desk)]:
                    (data/name).write_text(json.dumps(content),encoding="utf-8")
                old=pages_block(ROOT.parent/"github_original/.github/workflows/pages.yml")
                (data/"live.json").write_bytes(ACTUAL.read_bytes())
                (data/"desk-latest.json").write_text(json.dumps({"desks":{"world":[{}]*233}}),encoding="utf-8")
                with self.assertRaisesRegex(SystemExit,r"desk mismatch world: reported=None actual=233 floor=8"):
                    exec(old,{})
                (data/"desk-latest.json").write_text(json.dumps(merged_desk),encoding="utf-8")
                (data/"live.json").write_text(json.dumps(merged_live),encoding="utf-8")
                exec(pages_block(ROOT/".github/workflows/pages.yml"),{})
            finally:
                os.chdir(cwd)

    def test_preflight_holds_invalid_routes_sources_and_editorial_copy(self):
        for change in (
            lambda item: item.update(deskSlugs=["unknown"]),
            lambda item: item.update(sourceUrl=""),
            lambda item: item.update(body=""),
        ):
            live, _ = fixture()
            change(live["items"][0])
            self.assertTrue(publisher_errors(live))

    def test_daily_requires_same_checkpoint_before_generation(self):
        live,desk=fixture()
        merged_live,merged_desk=merge(live,desk)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"latest.json").write_text('{"date":"2020-01-01"}')
            (root/"desk-latest.json").write_text(json.dumps(merged_desk))
            (root/"live.json").write_text(json.dumps(live))
            with patch.object(daily,"DATA",root):
                with self.assertRaisesRegex(SystemExit,"DAILY_SCHEDULED_LIVE_DESK_CHECKPOINT_HOLD"):
                    daily.build()
                (root/"live.json").write_text(json.dumps(merged_live))
                anchor=datetime.fromisoformat(live["lastUpdated"]).astimezone(HKT)
                daytime=anchor.replace(hour=23,minute=59,second=0)
                edition, result=daily.build(now=daytime)
                self.assertTrue(result["changed"])
                self.assertEqual(edition["date"],live["date"])

    def test_registered_robot_reports_actual_contract_failure_and_reuses_audit(self):
        from publisher_recovery_robot import execute
        from test_publisher_recovery_robot import REGISTRY, CAT, cycle, SHA
        now = datetime.now(timezone.utc)
        source = json.loads(ACTUAL.read_bytes())
        live,desk = fixture()
        first = execute(REGISTRY,CAT,cycle(now),{},source,desk,{},{},SHA,now=now)
        self.assertEqual(first["performed"],"INSPECT_PUBLICATION_CONTRACT")
        self.assertIn("SCHEDULED_LIVE_CONTRACT_REJECTED",first["reasonCodes"])
        self.assertEqual(first["outcome"],"HOLD")
        telemetry = json.loads(json.dumps({"publisherRecoveryRobot": first,
                                            "publisherRecoveryAudit":[first]}))
        replay = execute(REGISTRY,CAT,cycle(now),{},source,desk,{},telemetry,SHA,now=now)
        self.assertEqual(first,replay)
        with self.assertRaisesRegex(ValueError,"EIC_ASSIGNMENT_SCOPE_HOLD"):
            execute(REGISTRY,CAT,dict(cycle(now),role="Not EIC"),{},live,desk,{},telemetry,SHA,now=now)

    def test_pages_receipt_requires_exact_deployed_json_and_html(self):
        from pages_publication_receipt import FILES, RECEIPT, build, verify
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); files={}
            for name in FILES:
                path=root/name;path.parent.mkdir(exist_ok=True,parents=True)
                files[name]=name.encode();path.write_bytes(files[name])
            expected=build(root,commit="a"*40,run_id="1",attempt="2")
            files[RECEIPT]=json.dumps(expected).encode()
            verify(files.__getitem__,expected)
            files["live.html"]=b"old but readable html"
            with self.assertRaisesRegex(ValueError,"hash mismatch: live.html"):
                verify(files.__getitem__,expected)
            files[RECEIPT]=json.dumps(dict(expected,sourceCommit="b"*40)).encode()
            with self.assertRaisesRegex(ValueError,"build receipt mismatch"):
                verify(files.__getitem__,expected)


if __name__=="__main__":
    unittest.main()
