"""Synthetic markup only: no source requests, generation or publication."""
import unittest
from unittest.mock import patch
from test_source_selection_budget import load_synthetic_module


class RthkArticleBodyTests(unittest.TestCase):
    def setUp(self):
        self.module = load_synthetic_module()
        self.url = "https://news.rthk.hk/rthk/ch/component/k2/1234567-20261009.htm"

    def extract(self, markup, url=None):
        with patch.object(self.module, "fetch", return_value=(url or self.url, markup.encode())):
            return self.module.extract_source_page(self.url)

    def test_actual_body_div_with_inline_words_and_nested_div_is_read(self):
        body = "合成正文甲" * 40 + "<span>合成</span><div>" + "合成正文乙" * 40 + "</div>"
        result = self.extract('<nav>导航秘密</nav><div class="itemFullText">' + body + '</div><p>页脚秘密</p>')
        self.assertIsNotNone(result)
        self.assertIn("合成正文甲", result[1])
        self.assertIn("合成正文乙", result[1])
        self.assertNotIn("秘密", result[1])

    def test_short_actual_body_cannot_be_padded_with_meta_or_chrome(self):
        markup = '<meta name="description" content="' + "无关描述" * 200 + '"><p>' + "无关页脚" * 200 + '</p><div class="itemFullText">正文太短</div>'
        self.assertIsNone(self.extract(markup))

    def test_script_style_and_nonarticle_divs_never_become_source_text(self):
        self.assertIsNone(self.extract('<div class="itemFullText"><script>' + "恶意指令" * 200 + '</script><style>' + "样式" * 200 + '</style><svg><text>秘密</text></svg>短正文</div><div>' + "无关导航" * 200 + '</div>'))

    def test_missing_exact_body_container_is_closed(self):
        for markup in ('<div class="itemFullTextFake">', '<div id="itemFullText">', '<article>'):
            self.assertIsNone(self.extract(markup + "合成正文" * 200))

    def test_parser_support_is_limited_to_exact_https_publisher_article(self):
        markup = '<div class="itemFullText">' + "合成正文" * 200 + '</div>'
        for url in ('https://example.invalid/rthk/ch/component/k2/1234567-20261009.htm', 'http://news.rthk.hk/rthk/ch/component/k2/1234567-20261009.htm', self.url + '?other=1', 'https://news.rthk.hk:444/rthk/ch/component/k2/1234567-20261009.htm', 'https://news.rthk.hk/other.htm'):
            with self.subTest(url=url):
                self.assertIsNone(self.extract(markup, url))

    def test_original_generic_paragraph_behavior_and_text_cap_are_retained(self):
        markup = '<p>' + "合成正文" * 3000 + '</p>'
        result = self.extract(markup, "https://example.invalid/article")
        self.assertEqual(len(result[1]), 9000)
        self.assertIsNone(self.extract('<div class="itemFullText">' + "短" * 299 + '</div>'))
        self.assertIsNotNone(self.extract('<div class="itemFullText">' + "字" * 300 + '</div>'))


if __name__ == "__main__":
    unittest.main()
