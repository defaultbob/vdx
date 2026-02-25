import os
import sys
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored

def run_push(args):
    state = load_state()
    ignore_patterns = load_ignore_patterns()
    base_dir = "components"
    
    if not os.path.exists(base_dir):
        print("No /components directory found.")
        sys.exit(1)
        
    print("Comparing local components to Vault state...")
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
        print("Everything up-to-date.")
        sys.exit(0)
        
    if getattr(args, 'dry_run', False):
        print("\n--- DRY RUN ---")
        for f, _, _ in modified_files: print(f"Would Push/Update: {f}")
        for ctype, cname in dropped_components: print(f"Would DROP: {ctype} {cname}")
        sys.exit(0)
        
    mdl_endpoint = f"/api/{API_VERSION}/mdl/execute"
    for file_path, local_mdl, local_checksum in modified_files:
        response = make_vault_request("POST", mdl_endpoint, data=local_mdl.encode('utf-8'))
        if response.status_code == 200 and response.json().get("responseStatus") == "SUCCESS":
            print(f"Pushed: {file_path}")
            state[file_path] = local_checksum
        else:
            print(f"Failed to push {file_path}: {response.text}")
            
    for ctype, cname in dropped_components:
        response = make_vault_request("POST", mdl_endpoint, data=f"DROP {ctype} {cname};".encode('utf-8'))
        if response.status_code == 200 and response.json().get("responseStatus") == "SUCCESS":
            print(f"Dropped: {ctype} {cname}")
        else:
            print(f"Failed to drop {ctype} {cname}: {response.text}")
            
    save_state(state)
    print("Push complete.")
