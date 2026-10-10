"""Synthetic locator/comment rejection; no network or publication writes."""
from datetime import datetime, timezone
from pathlib import Path
import copy
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import verified_draft_pending as ownership
import promote_verified_live_draft as publisher
from test_source_selection_budget import load_synthetic_module

NOW = datetime(2026, 10, 10, 3, 30, tzinfo=timezone.utc)


def draft(url="https://www.jiji.com/jc/article?k=2026101099999&g=pol&m=rss"):
    article = {field: "合成測試材料" * 25 for field in publisher.REQUIRED}
    article.update({"sourceName": "時事通信", "sourceUrl": url,
                    "sources": [{"name": "時事通信", "url": url}],
                    "body": "合成第一段" * 25 + "\n\n" + "合成第二段" * 25,
                    "publishedAt": "2026-10-10T01:00:00Z"})
    return {"status": "VERIFIED_DRAFT", "publicationType": "LIVE", "draftId": "synthetic",
            "createdAt": "2026-10-10T03:00:00Z", "targetPublication": "2026-10-10T11:00:00+08:00",
            "articles": [article]}


class LocatorIdentityTests(unittest.TestCase):
    def test_known_locator_host_case_subdomains_and_trailing_dot(self):
        for host in ("newspicks.com", "www.newspicks.com", "NEWSPICKS.COM", "newspicks.com."):
            self.assertTrue(ownership.locator_only_url("https://" + host + "/news/1/"))
        for url in ("https://www.jiji.com/jc/article", "https://jp.reuters.com/", "https://newspicks.com.example.invalid/"):
            self.assertFalse(ownership.locator_only_url(url))

    def test_locator_metadata_and_comments_cannot_pad_minimum(self):
        f = load_synthetic_module()
        html = '<meta name="description" content="合成摘要"><p>' + "合成讀者評論" * 300 + '</p>'
        with patch.object(f, "fetch", return_value=("https://newspicks.com/news/1/", html.encode())):
            self.assertIsNone(f.extract_source_page("https://newspicks.com/news/1/"))

    def test_redirect_to_locator_also_fails_before_model_evidence(self):
        f = load_synthetic_module()
        with patch.object(f, "fetch", return_value=("https://www.newspicks.com/news/1/", ("<p>" + "合成評論" * 300 + "</p>").encode())):
            self.assertIsNone(f.extract_source_page("https://example.com/locator"))

    def test_invalid_locator_draft_never_reserves_owner_production(self):
        value = draft("https://newspicks.com/news/1/")
        before = copy.deepcopy(value)
        self.assertFalse(ownership.pending_verified_draft(value, NOW, {}))
        self.assertEqual(value, before)

    def test_source_list_locator_cannot_hide_behind_original_wrapper(self):
        value = draft()
        value["articles"][0]["sources"][0]["url"] = "https://newspicks.com/news/1/"
        self.assertFalse(ownership.pending_verified_draft(value, NOW, {}))
        with self.assertRaisesRegex(SystemExit, "not publisher-body evidence"):
            publisher.validate_draft(value, NOW, 8, 90)

    def test_existing_legitimate_draft_and_publisher_timing_unchanged(self):
        value = draft()
        self.assertTrue(ownership.pending_verified_draft(value, NOW, {}))
        target, articles = publisher.validate_draft(value, NOW, 8, 90)
        self.assertEqual(target.isoformat(), value["targetPublication"])
        self.assertEqual(articles, value["articles"])
        with self.assertRaisesRegex(SystemExit, "target not past grace"):
            publisher.validate_draft(value, datetime(2026, 10, 10, 3, 7, tzinfo=timezone.utc), 8, 90)


if __name__ == "__main__":
    unittest.main()
