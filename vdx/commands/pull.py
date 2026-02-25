import os
import sys
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored

def run_pull(args):
    ignore_patterns = load_ignore_patterns()
    state = load_state()
    
    print("Pulling component configurations from Vault...")
    query = "SELECT component_name__sys, component_type__sys, mdl_definition__v FROM vault_component__v"
    endpoint = f"/api/{API_VERSION}/query/components"
    
    response = make_vault_request("POST", endpoint, data={"q": query})
    if response.status_code != 200:
        print(f"Error querying Vault: {response.text}")
        sys.exit(1)
        
    data = response.json()
    records = data.get("data", [])
    
    while data.get("responseDetails", {}).get("next_page"):
        next_url = data["responseDetails"]["next_page"]
        response = make_vault_request("GET", next_url)
        data = response.json()
        records.extend(data.get("data", []))
        
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
            print(f"Updated: {file_path}")

    for tracked_file in list(state.keys()):
        if tracked_file not in vault_components:
            if os.path.exists(tracked_file):
                os.remove(tracked_file)
                print(f"Deleted locally: {tracked_file}")
                deleted_count += 1
            del state[tracked_file]
            
    save_state(state)
    print(f"Pull complete. {updated_count} files updated. {deleted_count} files deleted.")
