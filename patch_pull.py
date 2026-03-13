import re

with open('vdx_project/vdx/commands/pull.py', 'r') as f:
    content = f.read()

# Replace imports
content = content.replace("from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored, sort_json_obj, format_mdl", 
"from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored, sort_json_obj, process_mdl_and_extract")

# Replace pull_mdl_components
old_func_start = "def pull_mdl_components(state, ignore_patterns):"
old_func_end = "def pull_java_sdk(state, ignore_patterns):"

before_func = content[:content.find(old_func_start)]
after_func = content[content.find(old_func_end):]

new_func = """def pull_mdl_components(state, ignore_patterns):
    \"\"\"Pulls MDL for 'metadata' class components.\"\"\"
    logging.info("Pulling MDL components...")
    vault_files = {}
    updated_count = 0

    # 1. Get component types for 'metadata' class
    logging.debug("Fetching component metadata to identify 'metadata' class types...")
    meta_endpoint = f"/api/{API_VERSION}/metadata/components"
    meta_response = make_vault_request("GET", meta_endpoint)
    meta_data = _handle_api_response(meta_response, "Component Metadata: ")
    if not meta_data:
        return {}, 0
    
    metadata_types = [
        comp["name"] for comp in meta_data.get("data", []) 
        if comp.get("class") == "metadata"
    ]
    
    if not metadata_types:
        logging.info("No 'metadata' class component types found.")
        return {}, 0
    
    # 2. Build and execute VQL query
    types_list = ", ".join([f"'{t}'" for t in metadata_types])
    query = f"SELECT component_name__v, component_type__v, mdl_definition__v FROM vault_component__v WHERE component_type__v CONTAINS ({types_list})"
    endpoint = f"/api/{API_VERSION}/query/components"
    response = make_vault_request("POST", endpoint, data={"q": query})
    data = _handle_api_response(response, "MDL Components: ")
    if not data:
        return {}, 0

    records = data.get("data", [])
    current_data = data
    while current_data.get("responseDetails", {}).get("next_page"):
        next_url = current_data["responseDetails"]["next_page"]
        logging.info("Traversing next page for MDL...")
        response = make_vault_request("GET", next_url)
        current_data = response.json()
        records.extend(current_data.get("data", []))

    base_dir = "components"
    pulled_types = set()
    for record in records:
        comp_type = record.get("component_type__v")
        if comp_type:
            pulled_types.add(comp_type)
            
    # Fetch metadata for each component type that was actually pulled
    component_metadata_cache = {}
    for comp_type in pulled_types:
        meta_endpoint = f"/api/{API_VERSION}/metadata/components/{comp_type}"
        meta_response = make_vault_request("GET", meta_endpoint)
        c_meta_data = _handle_api_response(meta_response, f"Metadata for {comp_type}: ")
        if c_meta_data:
            component_metadata_cache[comp_type] = c_meta_data
            file_path = os.path.join(base_dir, comp_type, f"METADATA-{comp_type}.json")
            if not is_ignored(file_path, ignore_patterns):
                vault_files[file_path] = True
                meta_content = json.dumps(sort_json_obj(c_meta_data), indent=2)
                if _update_local_file(file_path, meta_content, state):
                    updated_count += 1
                    
    # Process each component record with its metadata
    for record in records:
        comp_type = record.get("component_type__v")
        comp_name = record.get("component_name__v")
        mdl_def = record.get("mdl_definition__v", "")
        if not comp_type or not comp_name:
            logging.warning("Skipping record with missing name or type.")
            continue

        c_meta_data = component_metadata_cache.get(comp_type, {})
        
        mdl_def, extracted_files = process_mdl_and_extract(mdl_def, c_meta_data, comp_type, comp_name, base_dir)
        
        for ext_file_path, markup_clean in extracted_files.items():
            vault_files[ext_file_path] = True
            _update_local_file(ext_file_path, markup_clean, state)

        file_path = os.path.join(base_dir, comp_type, f"{comp_name}.mdl")
        if is_ignored(file_path, ignore_patterns):
            continue

        vault_files[file_path] = True
        if _update_local_file(file_path, mdl_def, state):
            updated_count += 1

    return vault_files, updated_count

"""

with open('vdx_project/vdx/commands/pull.py', 'w') as f:
    f.write(before_func + new_func + after_func)

