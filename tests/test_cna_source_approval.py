"""User-approved source boundary: synthetic metadata and HTML only, no network."""
from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import rolling_news_collector as collector
import general_news_verification_robot as robot
from test_source_selection_budget import load_synthetic_module
from test_direct_publisher_discovery import feed

NOW = datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc)
LINK = "https://www.cna.com.tw/news/aopl/202610099999.aspx"


class CnaApprovalTests(unittest.TestCase):
    def setUp(self):
        self.fallback = load_synthetic_module()

    def row(self, desk="japan"):
        return collector.cna_feed_items(feed(link=LINK, title="合成非新聞日本材料"), desk, NOW)[0]

    def test_metadata_only_and_required_attribution(self):
        row = self.row()
        self.assertEqual(row["source"], "中央通訊社")
        self.assertEqual(row["provider"], "CNA Official RSS")
        self.assertEqual(row["publishedAt"], "2026-10-09T14:00:00Z")
        self.assertEqual(set(row), {"id", "desk", "title", "url", "source", "provider", "query",
                                    "publishedAt", "firstSeenAt", "lastSeenAt"})
        self.assertNotIn("PRIVATE", str(row))
        self.assertTrue(self.fallback.trusted(row))
        self.assertTrue(collector.reviewed_direct_discovery(row, "japan"))

    def test_only_user_approved_asia_japan_and_exact_publisher_route_are_trusted(self):
        row = self.row()
        for delta in ({"source": "中央社未核准別名"}, {"provider": "unreviewed"}, {"desk": "world"},
                      {"url": LINK + "?tracking=1"}, {"url": LINK + "#fragment"},
                      {"url": LINK.replace("www.cna.com.tw", "www.cna.com.tw.evil.invalid")},
                      {"url": LINK.replace("https:", "http:")}, {"url": LINK.replace("/aopl/", "/aipl/")},
                      {"url": LINK.replace("www.cna.com.tw", "user@www.cna.com.tw")},
                      {"url": LINK.replace("www.cna.com.tw", "www.cna.com.tw:444")}):
            with self.subTest(delta=delta):
                candidate = {**row, **delta}
                self.assertFalse(self.fallback.trusted(candidate))
                self.assertFalse(collector.reviewed_direct_discovery(candidate, candidate["desk"]))
                self.assertLess(robot.candidate_score(candidate)[0], robot.candidate_score(row)[0])

    def test_missing_old_future_dates_and_wrong_regions_never_enter_staging(self):
        for date in ("", "unknown", "Thu, 08 Oct 2026 00:00:00 +0800", "Fri, 09 Oct 2026 23:30:00 +0800"):
            self.assertEqual(collector.cna_feed_items(feed(link=LINK, title="合成非新聞日本材料", date=date), "japan", NOW), [])
        self.assertEqual(collector.cna_feed_items(feed(link=LINK, title="合成非新聞印度材料"), "japan", NOW), [])
        self.assertEqual(collector.cna_feed_items(feed(link=LINK, title="合成非新聞日本材料"), "asia", NOW), [])
        with self.assertRaises(ValueError):
            collector.cna_feed_items(feed(link=LINK), "finance", NOW)

    def test_one_feed_read_per_cycle_and_honest_failure_without_private_error(self):
        with patch.object(collector, "now_utc", return_value=NOW), \
             patch.object(collector, "http_get", return_value=b"<rss><channel/></rss>"), \
             patch.object(collector, "direct_feed_get", return_value=b"<rss><channel/></rss>"), \
             patch.object(collector, "cna_feed_get", side_effect=TimeoutError("PRIVATE")) as get:
            result = collector.collect({})
        self.assertEqual(get.call_count, 2)
        get.assert_any_call()
        get.assert_any_call(collector.CNA_JAPAN_TOPIC)
        self.assertEqual([row["desk"] for row in result["errors"]], ["asia", "japan", "japan"])
        self.assertNotIn("PRIVATE", str(result))
        self.assertTrue(result["discoveryOnly"])
        self.assertEqual(result["maxCandidatesPerDesk"], 120)

    def test_japan_topic_metadata_requires_its_own_heading_and_explicit_clock(self):
        def page(date="2026-10-09T22:00:00+08:00", path="/news/aopl/202610099999.aspx", title="合成非新聞日本材料"):
            return ('<li><a href="' + path + '"><h2><span>' + title
                    + '</span></h2><time datetime="' + date + '">IGNORE DISPLAY TEXT</time></a></li>').encode()
        row = collector.cna_japan_topic_items(page(), NOW)[0]
        self.assertEqual(row["url"], LINK)
        self.assertEqual(row["source"], "中央通訊社")
        self.assertEqual(row["provider"], "CNA Official Japan Topic")
        self.assertEqual(row["publishedAt"], "2026-10-09T14:00:00Z")
        self.assertTrue(self.fallback.trusted(row))
        self.assertFalse(self.fallback.trusted({**row, "desk": "asia"}))
        for date in ("", "unknown", "2026-10-09", "2026-10-09T22:00:00", "2026-10-08T00:00:00+08:00", "2026-10-10T22:00:00+08:00"):
            self.assertEqual(collector.cna_japan_topic_items(page(date=date), NOW), [])
        for path in ("/news/aipl/202610099999.aspx", "https://evil.invalid/202610099999.aspx", "/news/aopl/202610099999.aspx?q=1"):
            self.assertEqual(collector.cna_japan_topic_items(page(path=path), NOW), [])
        self.assertEqual(collector.cna_japan_topic_items(page(title="合成非新聞印度材料"), NOW), [])
        self.assertEqual(collector.cna_japan_topic_items(b'<a href="/news/aopl/202610099999.aspx">undated</a>', NOW), [])

    def test_discovery_transport_refuses_arbitrary_routes_without_read(self):
        with patch.object(collector.urllib.request, "build_opener") as openers:
            with self.assertRaises(ValueError):
                collector.cna_feed_get("https://www.cna.com.tw/tag/9999/")
        openers.assert_not_called()

    def test_body_parser_excludes_meta_chrome_donations_ads_and_rss_padding(self):
        parser = self.fallback.CnaArticleBodyParser()
        parser.feed('<meta name="description" content="PRIVATE"><p>PRIVATE CHROME</p>'
                    '<div class="paragraph"><p>合成正文甲<a>內文</a></p>'
                    '<script>PRIVATE SCRIPT</script><p>合成正文乙</p></div>'
                    '<div class="paragraph appDownload"><p>PRIVATE DONATION</p></div>'
                    '<div class="paragraph articleADbox"><p>PRIVATE AD</p></div>')
        self.assertEqual("".join(parser.parts), "合成正文甲內文合成正文乙")
        self.assertEqual(parser.meta, [])

    def test_body_minimum_and_all_original_copy_gates_still_apply(self):
        with patch.object(self.fallback, "fetch", return_value=(LINK, b'<div class="paragraph"><p>short</p></div>')):
            self.assertIsNone(self.fallback.extract_source_page(LINK))
        self.assertEqual(self.fallback.MAX_SOURCE_PROBES, 12)
        self.assertEqual(self.fallback.MAX_MODEL_CALLS, 3)
        self.assertEqual(self.fallback.MAX_RUN_SECONDS, 600)


if __name__ == "__main__":
    unittest.main()
