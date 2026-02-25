import hashlib
import json
import os
import fnmatch

STATE_FILE = ".vdx_state.json"
IGNORE_FILE = ".vdxignore"

def compute_checksum(content):
    if content is None:
        return ""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def load_ignore_patterns():
    if os.path.exists(IGNORE_FILE):
        with open(IGNORE_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

def is_ignored(file_path, patterns):
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def load_dotenv(filepath=".env"):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                # Ignore empty lines and comments
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    val = val.strip().strip('\'"')
                    # Only set if not already present in the environment
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = val
