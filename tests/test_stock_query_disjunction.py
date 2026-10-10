"""Query-plan semantics only; no discovery, model or news writes."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rolling_news_collector as collector

EXPECTED = ['GOOG', 'GLDM', 'ICE', 'MCD', 'EMXC', 'GBTC', 'DBA', 'AAPL', 'EWY', 'META', 'MSFT', 'NVDA', 'TSM', 'PLTR', 'VT']
COMPANIES = {'GOOG', 'ICE', 'MCD', 'AAPL', 'META', 'MSFT', 'NVDA', 'TSM', 'PLTR'}


class StockQueryTests(unittest.TestCase):
    def test_order_count_and_twelve_hour_range_unchanged(self):
        queries = collector.QUERY_PLAN['stock-news']
        self.assertEqual(len(queries), 15)
        for symbol, query in zip(EXPECTED, queries):
            self.assertTrue(query.startswith('(' + symbol + ' OR '))
            self.assertTrue(query.endswith(' when:12h'))

    def test_company_identity_remains_required_with_explicit_topic_alternatives(self):
        for symbol, query in zip(EXPECTED, collector.QUERY_PLAN['stock-news']):
            if symbol not in COMPANIES:
                continue
            with self.subTest(symbol=symbol):
                self.assertRegex(query, r'^\([^()]+\) \([^()]+ OR [^()]+\) when:12h$')
                company, themes, _ = re.match(r'^(\([^()]+\)) (\([^()]+\)) (when:12h)$', query).groups()
                self.assertIn(symbol, company)
                self.assertNotIn('when:', themes)

    def test_discovery_is_not_publication_and_existing_floors_caps_unchanged(self):
        self.assertEqual(collector.MIN_DISCOVERY_PER_DESK['stock-news'], 12)
        self.assertEqual(collector.MAX_PER_DESK, 120)
        # Actual primary source/copy/15-symbol validation remains in the owner.
        workflow = (ROOT / '.github/workflows/stock-publication-maintenance.yml').read_text()
        self.assertIn('Build primary-source verified Stock draft', workflow)
        self.assertIn('Validate Stock News contract', workflow)
        self.assertIn('python scripts/validate_stock_news.py', workflow)
        self.assertIn('Candidates with an explicit publication time older than', (ROOT / 'scripts/rolling_news_collector.py').read_text())


if __name__ == '__main__':
    unittest.main()
