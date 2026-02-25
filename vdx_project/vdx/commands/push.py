import os
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
        
    mdl_endpoint = f"/api/mdl/execute"
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
