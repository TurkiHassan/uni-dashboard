"""Load existing credentials from the environment or user-local private storage."""
import json
import os
from pathlib import Path

def load_credentials():
    path = Path(__file__).resolve().parent.parent.parent / 'credentials' / 'blackboard-dashboard.json'
    try:
        saved = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        saved = {}
    user = os.environ.get('BLACKBOARD_USER') or os.environ.get('BB_USER') or saved.get('username', '')
    password = os.environ.get('BLACKBOARD_PASS') or os.environ.get('BB_PASS') or saved.get('password', '')
    return user, password
