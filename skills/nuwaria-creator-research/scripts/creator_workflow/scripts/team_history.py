"""Portable, minimal team dedup snapshot shipped with the private skill."""
import json
from pathlib import Path


def bundled_history():
    path = Path(__file__).resolve().parents[3] / 'assets/team_history.json'
    return json.loads(path.read_text(encoding='utf-8'))
