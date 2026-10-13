import sys
from pathlib import Path
import unittest

ENGINE = Path(__file__).resolve().parents[1] / 'skills/nuwaria-creator-research/scripts/creator_workflow'
sys.path.insert(0, str(ENGINE))
from outreach import Run


class DedupTests(unittest.TestCase):
    def test_exact_email_and_aliases(self):
        run = Run.__new__(Run)
        run.candidates = lambda: [{'handle': 'new_handle', 'aliases': ['old_handle'],
                                  'emails': ['Public@example.com'], 'name': 'Creator',
                                  'url': 'https://www.instagram.com/new_handle/'}]
        page = {'id': 'synthetic-page', 'properties': {
            '账号': {'type': 'rich_text', 'rich_text': [{'plain_text': '@old_handle'}]},
            '联系状态': {'type': 'select', 'select': {'name': '未联系'}}}}
        self.assertFalse(run.dedup([page], [])[0]['eligible'])
        self.assertFalse(run.dedup([], [{'messageId': 'test', 'toAddress': 'public@EXAMPLE.com'}])[0]['eligible'])
        self.assertTrue(run.dedup([], [{'messageId': 'test', 'toAddress': 'public@different.example'}])[0]['eligible'])


if __name__ == '__main__':
    unittest.main()
