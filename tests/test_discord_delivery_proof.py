"""Execute notification code with synthetic files and webhook; no external I/O."""
import ast
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import unittest
import urllib.request
from unittest.mock import Mock, patch

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/discord-notify.yml'
TEXT = WORKFLOW.read_text(encoding='utf-8')
CODE = TEXT.split("          python - <<'PY'\n", 1)[1].rsplit('          PY', 1)[0]
CODE = '\n'.join(line[10:] if line.startswith('          ') else line for line in CODE.splitlines())


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.current = {'lastUpdated': '2026-10-10T11:44:00+08:00', 'items': [
            {'id': 'new', 'title': '新稿', 'summary': '已核實', 'sourceUrl': 'https://source.example/article'}],
            'coverage': {'status': 'COMPLETE', 'rawFreshCandidateCount': 5}}
        self.previous = {**self.current, 'items': []}

    def execute(self, changed='data/live.json', failure=False):
        response = Mock(status=204)
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        stream = io.StringIO()

        def command(args, **kwargs):
            return changed if args[1] == 'diff-tree' else json.dumps(self.previous)

        with patch.dict(os.environ, {'GITHUB_EVENT_NAME': 'push', 'DISCORD_WEBHOOK_URL': 'https://synthetic.invalid/webhook'}, clear=True), \
             patch.object(Path, 'read_text', return_value=json.dumps(self.current)), \
             patch.object(subprocess, 'check_output', side_effect=command), \
             patch.object(urllib.request, 'urlopen', return_value=response, side_effect=TimeoutError('synthetic') if failure else None) as post, \
             contextlib.redirect_stdout(stream):
            try:
                exec(compile(CODE, '<synthetic-discord-workflow>', 'exec'), {})
            except SystemExit as exc:
                self.assertEqual(exc.code, 0)
            except TimeoutError:
                self.assertTrue(failure)
        return stream.getvalue(), post.call_count

    def test_complete_material_notification_proves_exact_snapshot(self):
        output, calls = self.execute()
        digest = hashlib.sha256(json.dumps(self.current, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        self.assertIn('DISCORD_LIVE_PUBLICATION_PROOF ' + digest, output)
        self.assertEqual(calls, 1)

    def test_webhook_timeout_has_no_proof_or_retry(self):
        output, calls = self.execute(failure=True)
        self.assertEqual(calls, 1)
        self.assertNotIn('DISCORD_LIVE_PUBLICATION_PROOF', output)

    def test_unchanged_live_is_no_send_no_proof(self):
        self.previous = self.current
        output, calls = self.execute()
        self.assertEqual(calls, 0)
        self.assertNotIn('DISCORD_LIVE_PUBLICATION_PROOF', output)

    def test_partial_delta_cannot_attest_entire_snapshot(self):
        unchanged = {'id': 'old', 'title': '舊稿', 'summary': '未改', 'sourceUrl': 'https://source.example/old'}
        self.current['items'].append(unchanged)
        self.previous['items'] = [unchanged]
        output, calls = self.execute()
        self.assertEqual(calls, 1)
        self.assertNotIn('DISCORD_LIVE_PUBLICATION_PROOF', output)

    def test_collection_failure_alert_cannot_be_publication_proof(self):
        self.previous = self.current
        self.current['coverage']['status'] = 'COLLECTION_FAILURE'
        output, calls = self.execute()
        self.assertEqual(calls, 1)
        self.assertNotIn('DISCORD_LIVE_PUBLICATION_PROOF', output)

    def test_daily_notification_is_not_live_publication_proof(self):
        self.current = {'date': '2026-10-10', 'articles': [], 'topFive': []}
        output, calls = self.execute(changed='data/latest.json')
        self.assertEqual(calls, 1)
        self.assertNotIn('DISCORD_LIVE_PUBLICATION_PROOF', output)

    def test_schedule_cache_keys_and_dispatch_policy_unchanged(self):
        self.assertIn('- cron: "12 * * * *"', TEXT)
        self.assertNotIn('workflow_run:', TEXT)
        self.assertNotIn('actions: write', TEXT)
        tree = ast.parse(CODE)
        proof_calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == 'live_publication_proof']
        self.assertEqual(len(proof_calls), 2)


if __name__ == '__main__':
    unittest.main()
