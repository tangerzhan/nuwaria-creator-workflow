"""Install the self-contained skill from a cloned repository or extracted ZIP."""
import argparse
from pathlib import Path
import shutil

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--skills-dir', type=Path, default=Path.home() / '.agents/skills')
args = parser.parse_args()
source = Path(__file__).resolve().parent / 'skills/nuwaria-creator-research'
target = args.skills_dir.expanduser().resolve() / source.name
if target.exists():
    parser.error('Skill already exists; review/rename the existing version before installing: ' + str(target))
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(source, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.venv'))
print('Installed: ' + str(target))
print('Install Python dependencies from ' + str(target / 'requirements.txt'))
print('Open Codex and invoke $nuwaria-creator-research. Restart Codex if it is not visible.')
