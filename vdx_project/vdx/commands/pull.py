import os
import sys
import logging
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored

def run_pull(args):
    """
    Fetches all component MDL definitions from Vault and synchronizes the local 
    /components directory.
    """
    ignore_patterns = load_ignore_patterns()
    state = load_state()
    
    logging.info("Pulling component configurations from Vault...")
    query = "SELECT component_name__v, component_type__v, mdl_definition__v FROM vault_component__v"
    endpoint = f"/api/{API_VERSION}/query/components"
    
    response = make_vault_request("POST", endpoint, data={"q": query})
    
    if response.status_code != 200:
        logging.error(f"Request failed with status {response.status_code}")
        sys.exit(1)
        
    data = response.json()
    if data.get("responseStatus") != "SUCCESS":
        logging.error(f"Vault API Error: {data.get('errors')}")
        sys.exit(1)
        
    records = data.get("data", [])
    logging.info(f"Fetched {len(records)} records from initial query.")
    
    # Handle pagination iteratively
    page_count = 1
    current_data = data
    while current_data.get("responseDetails", {}).get("next_page"):
        next_url = current_data["responseDetails"]["next_page"]
        logging.info(f"Traversing next page ({page_count})...")
        response = make_vault_request("GET", next_url)
        current_data = response.json()
        new_records = current_data.get("data", [])
        records.extend(new_records)
        page_count += 1
        
    logging.info(f"Total records retrieved: {len(records)}")
    
    base_dir = "components"
    os.makedirs(base_dir, exist_ok=True)
    
    vault_components = {}
    updated_count = 0
    deleted_count = 0
    
    for record in records:
        # Extract keys matching the SELECT clause exactly
        comp_type = record.get("component_type__v")
        comp_name = record.get("component_name__v")
        mdl_def = record.get("mdl_definition__v", "")
        
        if not comp_type or not comp_name:
            logging.warning("Skipping record with missing name or type.")
            continue
        
        type_dir = os.path.join(base_dir, comp_type)
        file_path = os.path.join(type_dir, f"{comp_name}.mdl")
        
        if is_ignored(file_path, ignore_patterns):
            logging.debug(f"Ignored by .vdxignore: {file_path}")
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

    # Remove local files that no longer exist in the Vault query results
    for tracked_file in list(state.keys()):
        if tracked_file not in vault_components:
            if os.path.exists(tracked_file):
                os.remove(tracked_file)
                logging.info(f"Deleted locally (not in Vault): {tracked_file}")
                deleted_count += 1
            del state[tracked_file]
            
    save_state(state)
    logging.info(f"Pull complete. {updated_count} files updated, {deleted_count} files removed.")