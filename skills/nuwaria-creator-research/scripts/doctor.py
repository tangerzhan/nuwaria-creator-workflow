"""Check local prerequisites; never open a browser or read credentials."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--project', type=Path)
args = parser.parse_args()
checks = {'Python >= 3.10': sys.version_info >= (3, 10)}
for module in ['requests', 'bs4', 'playwright', 'PIL', 'openpyxl']:
    checks[module] = importlib.util.find_spec(module) is not None
config = json.loads((args.project / 'project.json').read_text(encoding='utf-8-sig')) if args.project else {}
for name in ['ffmpeg', 'ffprobe']:
    directory = config.get('ffmpeg_bin')
    checks[name] = (Path(directory) / (name + '.exe' if sys.platform == 'win32' else name)).is_file() if directory else bool(shutil.which(name))
for key, ok in checks.items():
    print(('OK   ' if ok else 'MISS ') + key)
print('Chrome: launch a dedicated profile with remote debugging on loopback, then sign in manually.')
print('Notion/Zoho: optional, configure locally before using those commands. Credentials were not read.')
sys.exit(0 if all(checks.values()) else 1)
