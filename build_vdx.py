import os

# 1. Define the complete modularized vdx codebase
vdx_files = {
    "vdx_project/templates/vaultpackage.xml": r"""<?xml version="1.0" encoding="UTF-8"?>
<vaultPackage xmlns="https://veevavault.com/">
    <name>{package_name}</name>
    <source>
        <vaultId>LOCAL</vaultId>
        <author>{author}</author>
    </source>
    <package_type>migration__v</package_type>
    <summary>{summary}</summary>
    <description>{description}</description>
</vaultPackage>""",

    "vdx_project/vdx/__init__.py": "",

    "vdx_project/vdx/utils.py": r"""import hashlib
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
""",

    "vdx_project/vdx/auth.py": r"""import os
import json
import requests
import sys
import logging
from getpass import getpass

CONFIG_FILE = ".vdx_config"
API_VERSION = "v25.3"
CLIENT_ID = "veeva-vault-vdx-client"

def print_ascii_art():
    art = '''
 __     __  _____   __   __ 
 \ \   / / |  __ \  \ \ / / 
  \ \_/ /  | |  | |  \ V /  
   \   /   | |  | |   > <   
    \_/    |____/   /_/ \_\ 
    Vault Developer eXperience
    '''
    print(art) # Kept standard print so ascii isn't prefixed with logger formats

def login(dns=None, username=None, password=None, silent=False):
    if not silent:
        print_ascii_art()

    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

    dns = dns or os.getenv("VAULT_DNS") or config.get("vault_dns")
    username = username or os.getenv("VAULT_USERNAME") or config.get("username")
    password = password or os.getenv("VAULT_PASSWORD") or config.get("password")

    if not dns or not username:
        logging.error("Error: VAULT_DNS and VAULT_USERNAME are required.")
        sys.exit(1)
        
    if not password:
        password = getpass(f"Vault Password for {username}: ")

    url = f"https://{dns}/api/{API_VERSION}/auth"
    payload = {"username": username, "password": password}
    
    if not silent: logging.info(f"Authenticating to {dns}...")
    
    response = requests.post(url, data=payload, headers={"X-VaultAPI-ClientID": CLIENT_ID})
    
    if response.status_code == 200:
        session_id = response.json().get("sessionId")
        config = {
            "vault_dns": dns, 
            "username": username,
            "password": password,
            "session_id": session_id
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
            
        if not silent: logging.info("Login successful! Session and credentials saved locally.")
        return config
    else:
        logging.error(f"Login failed: {response.text}")
        sys.exit(1)

def get_config():
    if not os.path.exists(CONFIG_FILE):
        logging.error("Error: Not logged in. Run 'vdx login' first.")
        sys.exit(1)
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)
""",

    "vdx_project/vdx/api.py": r"""import requests
import logging
from vdx.auth import get_config, login, API_VERSION, CLIENT_ID

def make_vault_request(method, endpoint, **kwargs):
    config = get_config()
    
    # Check if a full URL was passed (like next_page URLs)
    if endpoint.startswith("http"):
        url = endpoint
    else:
        url = f"https://{config['vault_dns']}{endpoint}"
    
    headers = kwargs.pop('headers', {})
    headers["Authorization"] = config.get("session_id", "")
    headers["X-VaultAPI-ClientID"] = CLIENT_ID
    
    logging.debug(f"[API] Request: {method} {url}")
    if 'data' in kwargs and method != 'GET':
        data_str = str(kwargs['data'])
        # Truncate large payloads for readability in debug
        if len(data_str) > 200:
            data_str = data_str[:200] + " ... [TRUNCATED]"
        logging.debug(f"[API] Payload Preview: {data_str}")
        
    response = requests.request(method, url, headers=headers, **kwargs)
    logging.debug(f"[API] Response Status: {response.status_code}")
    
    # Vault sometimes returns HTTP 200 with FAILURE and INVALID_SESSION_ID in the body
    if response.status_code == 401 or "INVALID_SESSION_ID" in response.text:
        logging.info("Session expired. Automatically generating new session ID...")
        config = login(silent=True)
        headers["Authorization"] = config["session_id"]
        response = requests.request(method, url, headers=headers, **kwargs)
        logging.debug(f"[API] Retry Response Status: {response.status_code}")
        
    # Standardize error reporting at the API level (enforce responseStatus checking)
    try:
        resp_json = response.json()
        response_status = resp_json.get("responseStatus")
    except ValueError:
        response_status = None

    if response.status_code >= 400 or response_status == "FAILURE":
        logging.error(f"[API ERROR] HTTP {response.status_code} on {method} {url}")
        logging.error(f"[API ERROR] Response Body: {response.text}")
        
    return response
""",

    "vdx_project/vdx/commands/__init__.py": "",

    "vdx_project/vdx/commands/pull.py": r"""import os
import sys
import logging
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored

def run_pull(args):
    ignore_patterns = load_ignore_patterns()
    state = load_state()
    
    logging.info("Pulling component configurations from Vault...")
    query = "SELECT component_name__sys, component_type__sys, mdl_definition__v FROM vault_component__v"
    endpoint = f"/api/{API_VERSION}/query"
    
    response = make_vault_request("POST", endpoint, data={"q": query})
    if response.status_code != 200 or response.json().get("responseStatus") != "SUCCESS":
        logging.error(f"Error querying Vault: {response.text}")
        sys.exit(1)
        
    data = response.json()
    records = data.get("data", [])
    logging.info(f"Fetched {len(records)} records from initial query.")
    
    # Handle pagination iteratively with logging
    page_count = 1
    while data.get("responseDetails", {}).get("next_page"):
        next_url = data["responseDetails"]["next_page"]
        logging.info(f"Traversing next page ({page_count})...")
        response = make_vault_request("GET", next_url)
        data = response.json()
        new_records = data.get("data", [])
        records.extend(new_records)
        logging.debug(f"Fetched {len(new_records)} records from page {page_count}.")
        page_count += 1
        
    logging.info(f"Total records fetched from Vault: {len(records)}")
    
    base_dir = "components"
    os.makedirs(base_dir, exist_ok=True)
    
    vault_components = {}
    updated_count = deleted_count = 0
    
    for record in records:
        comp_type = record.get("component_type__sys", "unknown")
        comp_name = record.get("component_name__sys", "unknown")
        mdl_def = record.get("mdl_definition__v", "")
        
        type_dir = os.path.join(base_dir, comp_type)
        file_path = os.path.join(type_dir, f"{comp_name}.mdl")
        
        if is_ignored(file_path, ignore_patterns):
            logging.debug(f"Ignored tracking file based on '.vdxignore': {file_path}")
            continue
            
        vault_components[file_path] = True
        remote_checksum = compute_checksum(mdl_def)
        local_checksum = state.get(file_path, "")
        
        if local_checksum != remote_checksum:
            os.makedirs(type_dir, exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(mdl_def if mdl_def else "")
            state[file_path] = remote_checksum
            updated_count += 1
            logging.info(f"Updated: {file_path}")

    for tracked_file in list(state.keys()):
        if tracked_file not in vault_components:
            if os.path.exists(tracked_file):
                os.remove(tracked_file)
                logging.info(f"Deleted locally (removed from Vault): {tracked_file}")
                deleted_count += 1
            del state[tracked_file]
            
    save_state(state)
    logging.info(f"Pull complete. {updated_count} files updated. {deleted_count} files deleted.")
""",

    "vdx_project/vdx/commands/push.py": r"""import os
import sys
import logging
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored

def run_push(args):
    state = load_state()
    ignore_patterns = load_ignore_patterns()
    base_dir = "components"
    
    if not os.path.exists(base_dir):
        logging.error("No /components directory found.")
        sys.exit(1)
        
    logging.info("Comparing local components to Vault state...")
    modified_files = []
    dropped_components = []
    
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            file_path = os.path.join(root, file)
            if not file.endswith(".mdl") or is_ignored(file_path, ignore_patterns):
                continue
            with open(file_path, 'r', encoding='utf-8') as f:
                local_mdl = f.read()
            local_checksum = compute_checksum(local_mdl)
            if state.get(file_path) != local_checksum:
                modified_files.append((file_path, local_mdl, local_checksum))
                
    for tracked_file in list(state.keys()):
        if not os.path.exists(tracked_file):
            parts = tracked_file.split(os.sep)
            ctype, cname = parts[-2], parts[-1].replace(".mdl", "")
            dropped_components.append((ctype, cname))
            del state[tracked_file]
            
    if not modified_files and not dropped_components:
        logging.info("Everything up-to-date. No changes to push.")
        sys.exit(0)
        
    logging.info(f"Identified {len(modified_files)} modified files and {len(dropped_components)} dropped components.")
        
    if getattr(args, 'dry_run', False):
        logging.info("\n--- DRY RUN ---")
        for f, _, _ in modified_files: logging.info(f"Would Push/Update: {f}")
        for ctype, cname in dropped_components: logging.info(f"Would DROP: {ctype} {cname}")
        sys.exit(0)
        
    mdl_endpoint = f"/api/{API_VERSION}/mdl/execute"
    for file_path, local_mdl, local_checksum in modified_files:
        logging.debug(f"Pushing payload for {file_path} to Vault...")
        response = make_vault_request("POST", mdl_endpoint, data=local_mdl.encode('utf-8'))
        if response.status_code == 200 and response.json().get("responseStatus") == "SUCCESS":
            logging.info(f"Pushed: {file_path}")
            state[file_path] = local_checksum
        else:
            logging.error(f"Failed to push {file_path}: {response.text}")
            
    for ctype, cname in dropped_components:
        logging.debug(f"Dropping {ctype} {cname} from Vault...")
        response = make_vault_request("POST", mdl_endpoint, data=f"DROP {ctype} {cname};".encode('utf-8'))
        if response.status_code == 200 and response.json().get("responseStatus") == "SUCCESS":
            logging.info(f"Dropped: {ctype} {cname}")
        else:
            logging.error(f"Failed to drop {ctype} {cname}: {response.text}")
            
    save_state(state)
    logging.info("Push complete.")
""",

    "vdx_project/vdx/commands/package.py": r"""import os
import sys
import zipfile
import logging
from pathlib import Path
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum

def run_package(args):
    base_dir = "components"
    vpk_filename = "vdx_deployment.vpk"
    template_path = os.path.join("templates", "vaultpackage.xml")
    
    if not os.path.exists(base_dir):
        logging.error("No /components directory found.")
        sys.exit(1)
        
    logging.info(f"Packaging local components into {vpk_filename}...")
    
    with zipfile.ZipFile(vpk_filename, 'w', zipfile.ZIP_DEFLATED) as vpk:
        with open(template_path, 'r', encoding='utf-8') as tf:
            manifest_template = tf.read()
            
        manifest = manifest_template.format(
            package_name="vdx_deployment",
            author="vdx_tool",
            summary="Automated VPK generated by vdx",
            description="Custom VPK generated from local source control"
        )
        vpk.writestr("vaultpackage.xml", manifest)
        
        step_num = 10
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                if file.endswith(".mdl"):
                    file_path = os.path.join(root, file)
                    path_parts = Path(file_path).parts
                    comp_type = path_parts[-2]
                    comp_name = file.replace(".mdl", "")
                    
                    step_folder = f"{step_num:06d}"
                    with open(file_path, 'r', encoding='utf-8') as f:
                        mdl_content = f.read()
                        
                    md5_hash = compute_checksum(mdl_content)
                    
                    vpk.writestr(f"components/{step_folder}/{comp_type}.{comp_name}.mdl", mdl_content)
                    vpk.writestr(f"components/{step_folder}/{comp_type}.{comp_name}.md5", f"{md5_hash} {comp_type}.{comp_name}")
                    
                    step_num += 10
                    
    logging.info(f"Successfully created custom package {vpk_filename}.")
    logging.info("Importing VPK to Vault...")
    import_endpoint = f"/api/{API_VERSION}/vpackages"
    
    with open(vpk_filename, 'rb') as f:
        response = make_vault_request("POST", import_endpoint, files={'file': (vpk_filename, f, 'application/zip')})
        
    if response.status_code == 200 and response.json().get("responseStatus") == "SUCCESS":
        package_id = response.json().get("data", {}).get("package_id__v")
        logging.info(f"Package successfully imported. Vault Package ID: {package_id}")
        
        val_res = make_vault_request("POST", f"/api/{API_VERSION}/vpackages/{package_id}/actions/validate")
        if val_res.status_code == 200 and val_res.json().get("responseStatus") == "SUCCESS":
            logging.info(f"Validation Job initiated successfully.")
        else:
            logging.error(f"Failed to initiate validation job. Response: {val_res.text}")
    else:
        logging.error(f"Error importing package: {response.text}")
""",

    "vdx_project/vdx/cli.py": r"""import argparse
import logging
from vdx.auth import login
from vdx.commands.pull import run_pull
from vdx.commands.push import run_push
from vdx.commands.package import run_package
from vdx.utils import load_dotenv

def main():
    # Load .env variables into os.environ before anything else runs
    load_dotenv()

    parser = argparse.ArgumentParser(description="vdx - Veeva Vault Configuration Manager")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose/debug logging")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    login_parser = subparsers.add_parser("login", help="Authenticate to Vault")
    login_parser.add_argument("-u", "--username", help="Vault Username")
    login_parser.add_argument("-p", "--password", help="Vault Password")
    login_parser.add_argument("-v", "--vault-dns", help="Vault DNS")
    
    subparsers.add_parser("pull", help="Pull component MDLs from Vault")
    
    push_parser = subparsers.add_parser("push", help="Push local MDL changes to Vault")
    push_parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying")
    
    subparsers.add_parser("package", help="Create, import, and validate a VPK")
    
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(message)s')
    
    if args.command == "login":
        login(args.vault_dns, args.username, args.password)
    elif args.command == "pull":
        run_pull(args)
    elif args.command == "push":
        run_push(args)
    elif args.command == "package":
        run_package(args)
""",

    "vdx_project/main.py": r"""#!/usr/bin/env python3
from vdx.cli import main

if __name__ == "__main__":
    main()
"""
}

# 2. Automatically build the directory structure and write the files
print("Building vdx project directory...")
for file_path, content in vdx_files.items():
    # Ensure subdirectories exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # Write the Python code / XML string to file
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
        
print("Successfully generated all project files in the 'vdx_project' directory.")