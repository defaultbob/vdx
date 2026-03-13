import hashlib
import json
import os
import fnmatch
from pathlib import Path

STATE_FILE = ".vdx_state.json"
IGNORE_FILE = ".vdxignore"

def compute_checksum(content):
    if content is None:
        return ""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.md5(content).hexdigest()

def load_ignore_patterns():
    # We look for .vdxignore in the current working directory where the user runs the command
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

def sort_json_obj(obj):
    """
    Recursively sorts JSON objects to ensure deterministic output for version control.
    Dictionaries are sorted by their keys (when dumped with sort_keys=True).
    Lists of primitives or dictionaries with 'name' are sorted accordingly.
    """
    if isinstance(obj, dict):
        return {k: sort_json_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        sorted_list = [sort_json_obj(item) for item in obj]
        try:
            # If it's a list of dicts with 'name', sort by 'name'
            if all(isinstance(i, dict) and 'name' in i for i in sorted_list):
                return sorted(sorted_list, key=lambda x: x['name'])
            # For lists of primitives (strings, ints), sort normally
            return sorted(sorted_list, key=lambda x: json.dumps(x, sort_keys=True))
        except Exception:
            # Fallback to unsorted if elements are heterogeneous or uncomparable
            return sorted_list
    return obj

def load_dotenv(filepath=".env"):
    # Check current directory for .env
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    val = val.strip().strip('\'"')
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = val
