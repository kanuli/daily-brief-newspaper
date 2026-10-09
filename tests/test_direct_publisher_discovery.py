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
            collector.direct_feed_items(feed(), "world", NOW)

    def test_normal_collector_keeps_existing_queries_and_stages_only_discovery(self):
        queried = []
        def existing_provider(url):
            queried.append(url)
            return b"<rss><channel/></rss>"
        with patch.object(collector, "now_utc", return_value=NOW), \
             patch.object(collector, "http_get", side_effect=existing_provider), \
             patch.object(collector, "direct_feed_get", return_value=feed()) as direct:
            staged = collector.collect({})
        direct.assert_called_once_with(collector.DIRECT_PUBLISHER_FEEDS["hong-kong"])
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
        self.assertEqual(staged["errors"], [{"desk": "hong-kong", "provider": "RTHK Official RSS",
                                             "query": "official-publisher-rss", "error": "publisher-feed-unavailable"}])
        self.assertNotIn("PRIVATE", str(staged))
        self.assertEqual(sum(staged["candidateCounts"].values()), 0)

    def test_duplicate_candidate_keeps_original_discovery_identity_and_first_seen(self):
        rows = collector.direct_feed_items(feed(), "hong-kong", NOW)
        old = {**rows[0], "firstSeenAt": "2026-10-09T13:00:00Z"}
        merged = {"hong-kong": {old["id"]: old}}
        collector.merge_items("hong-kong", rows, merged, set())
        self.assertEqual(len(merged["hong-kong"]), 1)
        self.assertEqual(merged["hong-kong"][old["id"]]["firstSeenAt"], old["firstSeenAt"])


if __name__ == "__main__":
    unittest.main()
