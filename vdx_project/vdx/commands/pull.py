import os
import sys
import logging
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored

def run_pull(args):
    ignore_patterns = load_ignore_patterns()
    state = load_state()
    
    logging.info("Pulling component configurations from Vault...")
    query = "SELECT component_name__v, component_type__v, mdl_definition__v FROM vault_component__v"
    endpoint = f"/api/{API_VERSION}/query/components"
    
    response = make_vault_request("POST", endpoint, data={"q": query})
    logging.info(f"Response: {response.text}")
    
    if response.status_code != 200:
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
