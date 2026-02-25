import os
import sys
import logging
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored

def get_metadata_component_types():
    """
    Queries the Vault metadata API to find component types belonging to the 'metadata' class.
    """
    logging.info("Fetching component metadata to filter for 'metadata' class types...")
    endpoint = f"/api/{API_VERSION}/metadata/components"
    response = make_vault_request("GET", endpoint)
    
    if response.status_code != 200:
        logging.error("Failed to fetch component metadata.")
        return []
        
    data = response.json()
    if data.get("responseStatus") != "SUCCESS":
        logging.error(f"Metadata API Error: {data.get('errors')}")
        return []
        
    # Filter for components where class == "metadata"
    metadata_types = [
        comp["name"] for comp in data.get("data", []) 
        if comp.get("class") == "metadata"
    ]
    
    logging.debug(f"Identified {len(metadata_types)} metadata-class component types.")
    return metadata_types

def run_pull(args):
    """
    Fetches all component MDL definitions from Vault and synchronizes the local 
    /components directory using the specialized /query/components endpoint.
    """
    ignore_patterns = load_ignore_patterns()
    state = load_state()
    
    # Get the list of component types that are of class 'metadata'
    metadata_types = get_metadata_component_types()
    if not metadata_types:
        logging.error("No component types of class 'metadata' found. Aborting pull.")
        sys.exit(1)

    logging.info("Pulling component configurations from Vault...")
    
    # Use the requested query structure with __v fields
    types_list = ", ".join([f"'{t}'" for t in metadata_types])
    query = f"SELECT component_name__v, component_type__v, mdl_definition__v FROM vault_component__v WHERE component_type__v CONTAINS ({types_list})"
    
    # Use the specialized endpoint as requested
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
        # Extract keys matching the requested __v field names
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