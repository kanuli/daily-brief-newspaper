"""Offline owner-mode wiring regression; no collection or publication."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import newsroom_control_plane as control


class StockDiscoveryModeTests(unittest.TestCase):
    def test_missed_hour_uses_existing_deep_path_without_changing_duty_deadline(self):
        self.assertEqual(control.stock_duty_mode(50, 50), 'normal')
        self.assertEqual(control.stock_duty_mode(59.9, 50), 'normal')
        self.assertEqual(control.stock_duty_mode(60, 50), 'deep')
        self.assertEqual(control.stock_duty_mode(90, 50), 'deep')
        self.assertEqual(control.stock_duty_mode(70, 80), 'normal')
        self.assertEqual(control.stock_duty_mode(80, 80), 'deep')

    def test_deep_duty_selection_does_not_reset_the_existing_attempt_guard(self):
        source = (ROOT / 'scripts/newsroom_control_plane.py').read_text()
        self.assertIn('mode=stock_duty_mode(stock_age, stock_due)', source)
        self.assertIn('row["attempt"] = int(prior.get("attempt") or 1) + 1', source)
        self.assertIn('elif row["attempt"] >= 3:', source)
        self.assertIn('row["dispatchable"] = False', source)

    def test_owner_deep_mode_actually_selects_existing_deep_query_plan(self):
        workflow = (ROOT / '.github/workflows/stock-publication-maintenance.yml').read_text()
        command = re.search(r'if timeout 180s python scripts/rolling_news_collector.py(.*?); then', workflow, re.S).group(1)
        self.assertIn('--mode deep', command)
        self.assertIn('--output /tmp/search-staging-current.json', command)
        self.assertNotIn('--existing', command)
        self.assertIn('echo "STOCK_DEEP_DISCOVERY_REFRESH_FAILED rc=${rc}"', workflow)
        self.assertIn('exit "${rc}"', workflow)

    def test_normal_path_budget_and_contract_guards_remain(self):
        workflow = (ROOT / '.github/workflows/stock-publication-maintenance.yml').read_text()
        normal = re.search(r'elif timeout 120s python scripts/rolling_news_collector.py(.*?); then', workflow, re.S).group(1)
        self.assertIn('--existing /tmp/search-staging.json', normal)
        self.assertNotIn('--mode deep', normal)
        self.assertIn('len(queries) != len(required)', workflow)
        self.assertIn('Validate Stock News contract', workflow)
        self.assertIn('python scripts/validate_stock_news.py', workflow)
        self.assertLess(workflow.index('Validate Stock News contract'), workflow.index('git add -- data/stocks-latest.json'))

    def test_meaningful_stock_workflow_fix_wakes_owner_not_leaf(self):
        owner = (ROOT / '.github/workflows/editor-in-chief-newsroom-assignment.yml').read_text()
        self.assertIn('      - ".github/workflows/stock-publication-maintenance.yml"', owner)
        self.assertIn('Normal continuation is event-driven from robot completion', owner)


if __name__ == '__main__':
    unittest.main()
