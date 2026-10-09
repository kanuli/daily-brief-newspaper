"""Synthetic RSS only; no source retrieval, model, drafts or news writes."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rolling_news_collector as collector

NOW = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)
LINK = "https://news.rthk.hk/rthk/ch/component/k2/1999999-20261009.htm"


def feed(*, link=LINK, date="Fri, 09 Oct 2026 22:00:00 +0800", title="SYNTHETIC ONLY - NOT NEWS"):
    return ("<rss><channel><item><title>" + title + "</title><link>" + link
            + "</link><pubDate>" + date + "</pubDate><source>UNTRUSTED LABEL</source>"
            + "<description>PRIVATE SYNTHETIC BODY MUST NEVER BE STAGED</description>"
            + "</item></channel></rss>").encode()


class DirectDiscoveryTests(unittest.TestCase):
    def setUp(self):
        # Existing RTHK regressions must never make a new live publisher call.
        mocked = patch.object(collector, "cna_feed_get", return_value=b"<rss><channel/></rss>")
        mocked.start()
        self.addCleanup(mocked.stop)

    def test_metadata_has_direct_publisher_identity_but_no_copy_or_description(self):
        rows = collector.direct_feed_items(feed(), "hong-kong", NOW)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["url"], LINK)
        self.assertEqual(row["source"], "香港電台")
        self.assertEqual(row["provider"], "RTHK Official RSS")
        self.assertEqual(row["publishedAt"], "2026-10-09T14:00:00Z")
        self.assertEqual(set(row), {"id", "desk", "title", "url", "source", "provider", "query",
                                    "publishedAt", "firstSeenAt", "lastSeenAt"})
        self.assertNotIn("PRIVATE", str(row))

    def test_unknown_old_or_future_date_cannot_be_claimed_current(self):
        for date in ("", "unknown", "Thu, 08 Oct 2026 00:00:00 +0800", "Fri, 09 Oct 2026 23:30:00 +0800"):
            with self.subTest(date=date):
                self.assertEqual(collector.direct_feed_items(feed(date=date), "hong-kong", NOW), [])

    def test_unreviewed_links_or_article_paths_never_enter_trusted_feed_candidates(self):
        for link in ("http://news.rthk.hk/rthk/ch/component/k2/1999999-20261009.htm",
                     "https://news.rthk.hk.evil.invalid/rthk/ch/component/k2/1999999-20261009.htm",
                     "https://user:secret@news.rthk.hk/rthk/ch/component/k2/1999999-20261009.htm",
                     "https://news.rthk.hk:444/rthk/ch/component/k2/1999999-20261009.htm",
                     "https://news.rthk.hk/rthk/ch/rss.htm", "http://127.0.0.1/private"):
            with self.subTest(link=link):
                self.assertEqual(collector.direct_feed_items(feed(link=link), "hong-kong", NOW), [])

    def test_arbitrary_url_or_desk_is_rejected_without_network(self):
        with self.assertRaises(ValueError):
            collector.direct_feed_get("https://unreviewed.invalid/feed")
        with self.assertRaises(ValueError):
            collector.direct_feed_items(feed(), "football", NOW)

    def test_normal_collector_keeps_existing_queries_and_stages_only_discovery(self):
        queried = []
        def existing_provider(url):
            queried.append(url)
            return b"<rss><channel/></rss>"
        with patch.object(collector, "now_utc", return_value=NOW), \
             patch.object(collector, "http_get", side_effect=existing_provider), \
             patch.object(collector, "direct_feed_get", return_value=feed()) as direct:
            staged = collector.collect({})
        self.assertEqual(direct.call_count, 3)
        direct.assert_any_call(collector.DIRECT_PUBLISHER_FEEDS["hong-kong"])
        direct.assert_any_call(collector.DIRECT_PUBLISHER_FEEDS["finance"])
        self.assertEqual(sum("news.google.com" in url for url in queried), sum(map(len, collector.QUERY_PLAN.values())))
        self.assertIs(staged["discoveryOnly"], True)
        self.assertIs(staged["verificationRequiredBeforePublish"], True)
        self.assertEqual(staged["queryAudit"]["hong-kong"]["directPublisherItems"], 1)
        self.assertEqual(staged["candidateCounts"]["hong-kong"], 1)
        self.assertEqual(staged["discoveryFloors"], collector.MIN_DISCOVERY_PER_DESK)

    def test_direct_transport_failure_does_not_dispatch_or_replace_normal_provider(self):
        with patch.object(collector, "now_utc", return_value=NOW), \
             patch.object(collector, "http_get", return_value=b"<rss><channel/></rss>"), \
             patch.object(collector, "direct_feed_get", side_effect=TimeoutError("PRIVATE")):
            staged = collector.collect({})
        self.assertEqual(staged["errors"], [{"desk": desk, "provider": "RTHK Official RSS",
                                             "query": "official-publisher-rss", "error": "publisher-feed-unavailable"}
                                            for desk in ("world", "asia", "hong-kong", "japan", "finance", "ai-tech")])
        self.assertNotIn("PRIVATE", str(staged))
        self.assertEqual(sum(staged["candidateCounts"].values()), 0)

    def test_duplicate_candidate_keeps_original_discovery_identity_and_first_seen(self):
        rows = collector.direct_feed_items(feed(), "hong-kong", NOW)
        old = {**rows[0], "firstSeenAt": "2026-10-09T13:00:00Z"}
        merged = {"hong-kong": {old["id"]: old}}
        collector.merge_items("hong-kong", rows, merged, set())
        self.assertEqual(len(merged["hong-kong"]), 1)
        self.assertEqual(merged["hong-kong"][old["id"]]["firstSeenAt"], old["firstSeenAt"])

    def test_finance_feed_is_independent_discovery_with_unchanged_source_verification_requirement(self):
        row = collector.direct_feed_items(feed(), "finance", NOW)[0]
        self.assertEqual(row["desk"], "finance")
        self.assertEqual(row["source"], "香港電台")
        self.assertNotIn("verified", row)

    def test_regions_require_explicit_title_evidence_and_do_not_cross_route(self):
        fixtures = {"world": "合成測試非新聞資料美國", "asia": "合成測試非新聞資料新加坡",
                    "japan": "合成測試非新聞資料日本", "ai-tech": "合成測試非新聞資料人工智能"}
        for expected, title in fixtures.items():
            for desk in fixtures:
                with self.subTest(expected=expected, desk=desk):
                    self.assertEqual(collector.direct_title_routed(title, desk), desk == expected)
        for desk in fixtures:
            self.assertFalse(collector.direct_title_routed("合成未知地區材料並非新聞", desk))

    def test_japan_region_takes_precedence_over_asia_and_world_without_output_rewriting(self):
        title = "合成測試非新聞資料日本與美國"
        self.assertTrue(collector.direct_title_routed(title, "japan"))
        self.assertFalse(collector.direct_title_routed(title, "world"))
        self.assertFalse(collector.direct_title_routed(title, "asia"))
        rows = collector.direct_feed_items(feed(title=title), "japan", NOW)
        self.assertEqual(rows[0]["title"], title)

    def test_shared_feed_transport_is_not_retried_once_per_desk_on_failure(self):
        with patch.object(collector, "now_utc", return_value=NOW), \
             patch.object(collector, "http_get", return_value=b"<rss><channel/></rss>"), \
             patch.object(collector, "direct_feed_get", side_effect=TimeoutError("PRIVATE")) as direct:
            collector.collect({})
        self.assertEqual(direct.call_count, 3)

    def test_search_duplicate_cannot_replace_direct_url_or_refresh_publisher_date(self):
        row = collector.direct_feed_items(feed(), "hong-kong", NOW)[0]
        merged = {"hong-kong": {row["id"]: dict(row)}}
        wrapped = {**row, "provider": "Google News RSS", "url": "https://news.google.com/rss/articles/synthetic",
                   "publishedAt": "2026-10-09T14:59:00Z", "lastSeenAt": "2026-10-09T15:00:00Z"}
        collector.merge_items("hong-kong", [wrapped], merged, set())
        saved = merged["hong-kong"][row["id"]]
        self.assertEqual(saved["url"], row["url"])
        self.assertEqual(saved["publishedAt"], row["publishedAt"])
        self.assertEqual(saved["provider"], "RTHK Official RSS")
        self.assertEqual(saved["lastSeenAt"], wrapped["lastSeenAt"])

    def test_source_access_preference_preserves_same_reservoir_cap_without_retiming(self):
        base = collector.direct_feed_items(feed(), "hong-kong", NOW)[0]
        generic = [{**base, "id": "synthetic-" + str(i), "provider": "Synthetic Discovery",
                    "source": "Synthetic", "url": "https://example.invalid/" + str(i),
                    "title": "SYNTHETIC ONLY NOT NEWS " + str(i), "publishedAt": "2026-10-09T14:59:00Z"}
                   for i in range(125)]
        with patch.object(collector, "now_utc", return_value=NOW), \
             patch.object(collector, "http_get", return_value=b"<rss><channel/></rss>"), \
             patch.object(collector, "direct_feed_get", return_value=feed()):
            result = collector.collect({"desks": {"hong-kong": generic}})
        rows = result["desks"]["hong-kong"]
        self.assertEqual(len(rows), 120)
        self.assertEqual(rows[0]["id"], base["id"])
        self.assertEqual(rows[0]["publishedAt"], "2026-10-09T14:00:00Z")
        self.assertEqual(result["maxCandidatesPerDesk"], 120)

    def test_untrusted_provider_label_cannot_grant_reservoir_preference(self):
        row = collector.direct_feed_items(feed(), "hong-kong", NOW)[0]
        for delta in ({"source": "Untrusted"}, {"url": "http://127.0.0.1/private"},
                      {"publishedAt": None}, {"provider": "unreviewed"}):
            with self.subTest(delta=delta):
                self.assertFalse(collector.reviewed_direct_discovery({**row, **delta}, "hong-kong"))


if __name__ == "__main__":
    unittest.main()
