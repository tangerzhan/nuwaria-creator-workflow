import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/nuwaria-creator-research'


class TeamHistoryTests(unittest.TestCase):
    def test_installed_snapshot_blocks_history_and_survives_refresh(self):
        snapshot = json.loads((SKILL / 'assets/team_history.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as tmp:
            def run(*args):
                subprocess.run([sys.executable, '-X', 'utf8', *map(str, args)], check=True, capture_output=True)
            run(ROOT / 'install.py', '--skills-dir', Path(tmp) / 'skills')
            scripts = Path(tmp) / 'skills/nuwaria-creator-research/scripts'
            run(scripts / 'setup_workspace.py', '--workspace', Path(tmp) / 'work', '--date', '2026-10-13')
            project = Path(tmp) / 'work/candidate_research_2026-10-13'
            handle = next(h for h in snapshot['handles'] if not h.startswith('tt__') and len(h) <= 30)
            held = next(h for h in snapshot['screening'] if h not in snapshot['handles'] and len(h) <= 30)
            queue = [{'handle': handle}, {'handle': held}, {'handle': 'test_unique_email_match_728', 'email': snapshot['emails'][0]}, {'handle': 'test_new_creator_928173'}]
            (project / 'queue.json').write_text(json.dumps(queue), encoding='utf-8')
            base = [scripts / 'creator_workflow/workflow.py', '--project', project, 'queue-check', 'queue.json']
            for _ in range(2):
                run(*base)
                result = json.loads((project / 'queue_preflight.json').read_text(encoding='utf-8'))
                self.assertEqual(result['ready_count'], 1)
                reasons = {r['reason'] for r in result['skipped']}
                self.assertIn('historical_handle_or_alias', reasons)
                self.assertIn('historical_email', reasons)
                self.assertTrue(any(r.startswith('historical_screening_') for r in reasons))
            (project / 'screening.json').write_text(json.dumps({held: {'verdict': 'pass', 'reason': 'new evidence'}}), encoding='utf-8')
            run(*base)
            self.assertEqual(json.loads((project / 'queue_preflight.json').read_text())['ready_count'], 2)
