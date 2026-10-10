"""Synthetic official-feed identity/body tests; no network or model calls."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import rolling_news_collector as collector
import general_news_verification_robot as robot
from test_source_selection_budget import load_synthetic_module, request

NOW = datetime(2026, 10, 10, 3, tzinfo=timezone.utc)
LINK = "https://www.jiji.com/jc/article?k=2026101099999&g=pol&m=rss"
EMPTY = b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"/>'


def feed(link=LINK, date="2026-10-10T10:00:00+09:00"):
    return ('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
            'xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<item><title>合成非新聞政治材料標題</title><link>' + link.replace("&", "&amp;") + '</link>'
            '<dc:date>' + date + '</dc:date><description>PRIVATE RSS BODY</description></item></rdf:RDF>').encode()


class JijiSourceTests(unittest.TestCase):
    def setUp(self):
        self.fallback = load_synthetic_module()

    def test_exact_domestic_source_metadata_and_ranking(self):
        row = collector.jiji_feed_items(feed(), NOW)[0]
        self.assertEqual(row["source"], "時事通信")
        self.assertEqual(row["publishedAt"], "2026-10-10T01:00:00Z")
        self.assertNotIn("PRIVATE", str(row))
        self.assertTrue(collector.reviewed_direct_discovery(row, "japan"))
        self.assertTrue(self.fallback.trusted(row))
        self.assertEqual(robot.candidate_score(row)[0], 8)

    def test_no_foreign_categories_credentials_tracking_or_lookalike_hosts(self):
        for link in (LINK.replace("g=pol", "g=int"), LINK.replace("g=pol", "g=eco"),
                     LINK.replace("www.jiji.com", "www.jiji.com.evil.invalid"),
                     LINK.replace("www.jiji.com", "user@www.jiji.com"),
                     LINK.replace("https:", "http:"), LINK.replace("2026101099999", "202610109999"),
                     LINK + "&other=1", LINK + "#fragment"):
            self.assertEqual(collector.jiji_feed_items(feed(link=link), NOW), [])

    def test_missing_timezone_stale_future_and_invalid_dates_are_rejected(self):
        for date in ("", "invalid", "2026-10-10T10:00:00", "2026-10-09T11:59:59+09:00", "2026-10-10T12:00:01+09:00"):
            self.assertEqual(collector.jiji_feed_items(feed(date=date), NOW), [])

    def test_source_provider_or_desk_mismatch_cannot_get_direct_preference(self):
        row = collector.jiji_feed_items(feed(), NOW)[0]
        for change in ({"source": "unreviewed"}, {"provider": "Search"}, {"desk": "world"}):
            self.assertFalse(collector.reviewed_direct_discovery({**row, **change}, "japan"))
            self.assertLess(robot.candidate_score({**row, **change})[0], 8)

    def test_worker_preserves_exact_direct_priority_inside_original_probe_budget(self):
        data = request(["japan", "finance"])
        data["candidates"].append(collector.jiji_feed_items(feed(), NOW)[0])
        before = str(data)
        queue = self.fallback.bounded_source_queue(data)
        self.assertEqual(queue[0]["url"], LINK)
        self.assertEqual(queue[1]["desk"], "finance")
        self.assertEqual(len(queue), 8)
        self.assertEqual(str(data), before)
        self.assertEqual(self.fallback.MAX_CANDIDATES_PER_DESK, 4)
        self.assertEqual(self.fallback.MAX_SOURCE_PROBES, 12)
        self.assertEqual(self.fallback.MAX_MODEL_CALLS, 3)

    def test_worker_direct_priority_cannot_be_claimed_by_wrong_provider_or_route(self):
        for change in ({"provider": "Search"}, {"url": LINK + "&other=1"}, {"desk": "world"}):
            row = {**collector.jiji_feed_items(feed(), NOW)[0], **change}
            data = request(["japan", "finance"])
            data["candidates"][0]["source"] = "NHK"
            data["candidates"].append(row)
            self.assertEqual(self.fallback.bounded_source_queue(data)[0]["source"], "NHK")

    def test_only_article_paragraphs_no_captions_meta_ads_or_related_links(self):
        body = "正文測試" * 90
        html = ('<meta name="description" content="PRIVATE META"><p>PRIVATE NAV</p>'
                '<div class="ArticleText clearfix"><figure><figcaption><p>PRIVATE CAPTION</p></figcaption></figure>'
                '<aside><div><p>PRIVATE AD</p></div></aside><p>正文<b>測試</b>' + body + '</p>'
                '<p class="ArticleTextTab"><a>PRIVATE RELATED</a></p><script>PRIVATE SCRIPT</script>'
                '</div><p>PRIVATE FOOTER</p>')
        with patch.object(self.fallback, "fetch", return_value=(LINK, html.encode())):
            result = self.fallback.extract_source_page(LINK)
        self.assertIsNotNone(result)
        self.assertNotIn("PRIVATE", result[1])
        self.assertTrue(result[1].replace(" ", "").startswith("正文測試"))

    def test_chrome_or_related_links_cannot_pad_original_source_minimum(self):
        html = '<div class="ArticleText"><p>短文</p><aside><p>' + "廣告" * 400 + '</p></aside><p class="ArticleTextTab">' + "關聯" * 400 + '</p></div>'
        with patch.object(self.fallback, "fetch", return_value=(LINK, html.encode())):
            self.assertIsNone(self.fallback.extract_source_page(LINK))

    def test_no_article_container_fails_original_body_minimum(self):
        with patch.object(self.fallback, "fetch", return_value=(LINK, ('<p>' + "測試" * 400 + '</p>').encode())):
            self.assertIsNone(self.fallback.extract_source_page(LINK))

    def test_collector_failure_remains_discovery_only_and_keeps_original_search(self):
        with patch.object(collector, "now_utc", return_value=NOW), \
             patch.object(collector, "http_get", return_value=b"<rss><channel/></rss>"), \
             patch.object(collector, "direct_feed_get", return_value=b"<rss><channel/></rss>"), \
             patch.object(collector, "cna_feed_get", return_value=b"<rss><channel/></rss>"), \
             patch.object(collector, "jiji_feed_get", side_effect=TimeoutError("PRIVATE")) as get:
            data = collector.collect({})
        self.assertEqual(get.call_count, 1)
        self.assertTrue(data["discoveryOnly"])
        self.assertTrue(data["verificationRequiredBeforePublish"])
        self.assertEqual(data["maxCandidatesPerDesk"], 120)
        self.assertEqual(data["queryAudit"]["japan"]["queries"], len(collector.QUERY_PLAN["japan"]))
        self.assertNotIn("PRIVATE", str(data))
        self.assertTrue(any(row["provider"] == "Jiji Official RSS" for row in data["errors"]))


if __name__ == "__main__":
    unittest.main()
