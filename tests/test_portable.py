import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/nuwaria-creator-research'
SCRIPTS = SKILL / 'scripts'
ENGINE = SCRIPTS / 'creator_workflow'
sys.path.insert(0, str(ENGINE))
spec = importlib.util.spec_from_file_location('setup_workspace', SCRIPTS / 'setup_workspace.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class PortableTests(unittest.TestCase):
    def cli(self, *args, expected=0):
        result = subprocess.run([sys.executable, '-X', 'utf8', *map(str, args)],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout

    def test_fresh_workspace_status_draft_and_existing_protection(self):
        with tempfile.TemporaryDirectory(prefix='creator smoke ') as tmp:
            project = setup.initialize(Path(tmp) / '工作区 with spaces', '2026-10-12', 2)
            config = json.loads((project / 'project.json').read_text(encoding='utf-8'))
            self.assertEqual(config['history_projects'], [])
            self.assertEqual(config['notion_data_source'], '')
            base = [ENGINE / 'workflow.py', '--project', project]
            status = json.loads(self.cli(*base, 'status'))
            self.assertEqual(status['included'], 0)
            self.cli(*base, 'check')
            self.cli(*base, 'export', '--draft')
            self.assertTrue(list(project.glob('*.xlsx')))
            self.cli(*base, 'check', '--complete', expected=1)
            with self.assertRaises(FileExistsError):
                setup.initialize(project.parent, '2026-10-12', 2)
            next_project = project.parent / 'candidate_research_2026-10-13'
            self.cli(ENGINE / 'workflow.py', '--project', next_project, 'init',
                     '--date', '2026-10-13', '--target', '2', '--from-project', project)
            after = json.loads((next_project / 'project.json').read_text(encoding='utf-8'))
            self.assertIn(str(project), after['history_projects'])
            self.assertEqual(json.loads((next_project / 'production_reviews.json').read_text()), {})
            self.assertEqual(json.loads((next_project / 'contact_email_aliases.json').read_text()), [])

    def test_ffmpeg_binary_resolution_uses_native_platform_and_path(self):
        with tempfile.TemporaryDirectory(prefix='creator tools ') as tmp:
            project = setup.initialize(Path(tmp) / 'workspace', '2026-10-12')
            code = '''
import sys, os
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, sys.argv[1])
os.environ['CREATOR_PROJECT'] = sys.argv[2]
import fast_audit
fast_audit.FF = None
with patch('fast_audit.shutil.which', return_value='/usr/local/bin/ffmpeg'):
    assert fast_audit.executable('ffmpeg') == '/usr/local/bin/ffmpeg'
fast_audit.FF = Path(sys.argv[3])
fast_audit.FF.mkdir()
name = 'ffmpeg.exe' if os.name == 'nt' else 'ffmpeg'
(fast_audit.FF/name).write_text('fake executable fixture')
assert Path(fast_audit.executable('ffmpeg')).name == name
try:
    fast_audit.executable('ffprobe')
except FileNotFoundError:
    pass
else:
    raise AssertionError('missing configured binary must fail')
'''
            self.cli('-c', code, ENGINE / 'scripts', project, Path(tmp) / 'media tools')

    def test_install_zip_layout_without_github(self):
        with tempfile.TemporaryDirectory(prefix='creator install ') as tmp:
            self.cli(ROOT / 'install.py', '--skills-dir', tmp)
            installed = Path(tmp) / 'nuwaria-creator-research'
            self.assertTrue((installed / 'scripts/creator_workflow/workflow.py').is_file())
            self.assertTrue((installed / 'assets/schema.json').is_file())
            self.cli(ROOT / 'install.py', '--skills-dir', tmp, expected=2)
            project = Path(tmp) / 'workspace'
            self.cli(installed / 'scripts/setup_workspace.py', '--workspace', project,
                     '--date', '2026-10-12')
            self.cli(installed / 'scripts/creator_workflow/workflow.py', '--project',
                     project / 'candidate_research_2026-10-12', 'check')

    def test_no_live_identifiers_in_skill(self):
        import re
        uuid = re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b')
        for path in SKILL.rglob('*'):
            if path.suffix not in {'.py', '.json', '.md', '.txt'}:
                continue
            text = path.read_text(encoding='utf-8')
            self.assertFalse(uuid.search(text), str(path))
            self.assertNotIn('D:/Codex', text, str(path))
            self.assertNotIn('support@nuwaria.com', text, str(path))


if __name__ == '__main__':
    unittest.main()
