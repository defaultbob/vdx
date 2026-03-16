import os
import sys
import logging
import difflib
from pathlib import Path
import json
import tempfile

from vdx.api import make_vault_request, API_VERSION
from vdx.utils import load_state, compute_checksum, reassemble_component

def get_vault_mdl_content(component_type, component_name):
    """
    Fetches the MDL content for a single component from Vault.
    """
    query = f"SELECT mdl_definition__v FROM vault_component__v WHERE component_type__v = '{component_type}' AND component_name__v = '{component_name}'"
    endpoint = f"/api/{API_VERSION}/query/components"
    response = make_vault_request("POST", endpoint, data={"q": query})
    
    if response.status_code == 200:
        data = response.json()
        if data.get("responseStatus") == "SUCCESS" and data.get("data"):
            # Format the original MDL from Vault so the diff is against formatted code
            from vdx.utils import format_mdl
            raw_mdl = data["data"][0].get("mdl_definition__v", "")
            return format_mdl(raw_mdl)
    logging.warning(f"Could not fetch original content for {component_type}.{component_name}")
    return None

def run_patch(args):
    base_dir = "components"
    patch_filename = "vdx_patch.patch"
    
    if not os.path.exists(base_dir):
        logging.error("No /components directory found in the current directory.")
        sys.exit(1)

    state = load_state()
    logging.info("Analyzing local components for changes...")
    
    components_to_patch = set()
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".mdl") or file.endswith(".xml") or file.endswith(".json") or file.endswith(".html") or file.endswith(".as"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    current_checksum = compute_checksum(content)
                    if state.get(file_path) != current_checksum:
                        parts = Path(file_path).parts
                        if len(parts) >= 3:
                            comp_type = parts[1]
                            comp_name = parts[2]
                            if comp_name.endswith('.mdl'):
                                comp_name = comp_name[:-4]
                            components_to_patch.add((comp_type, comp_name))
                except Exception:
                    pass

    if not components_to_patch:
        if args.json:
            print("[]")
        else:
            logging.info("No modified components found.")
        sys.exit(0)

    if args.json:
        json_output = []
        for comp_type, comp_name in components_to_patch:
            current_content = reassemble_component(base_dir, comp_type, comp_name)
            original_content = get_vault_mdl_content(comp_type, comp_name)
            
            if original_content is not None and current_content is not None:
                # Write original to a temp file
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix=".mdl") as tmp:
                    tmp.write(original_content)
                    original_file_path = tmp.name
                
                # Write current reassembled content to a temp file to compare against
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix=".mdl") as tmp2:
                    tmp2.write(current_content)
                    modified_file_path = tmp2.name
                
                # We show the component dir as the path in JSON output for UI purposes
                comp_dir = os.path.join(base_dir, comp_type, comp_name)
                json_output.append({
                    "file_path": comp_dir,
                    "original_file": original_file_path,
                    "modified_file": modified_file_path
                })
        print(json.dumps(json_output, indent=2))
        sys.exit(0)


    logging.info(f"Found {len(components_to_patch)} modified root components. Generating patch...")

    all_diffs = []
    for comp_type, comp_name in components_to_patch:
        current_content = reassemble_component(base_dir, comp_type, comp_name)
        original_content = get_vault_mdl_content(comp_type, comp_name)
        
        if original_content is not None and current_content is not None:
            comp_path = f"{base_dir}/{comp_type}/{comp_name}"
            diff = difflib.unified_diff(
                original_content.splitlines(keepends=True),
                current_content.splitlines(keepends=True),
                fromfile=f"a/{comp_path}",
                tofile=f"b/{comp_path}",
            )
            all_diffs.extend(list(diff))

    if not all_diffs:
        logging.info("Could not generate diffs for modified files. This might be due to issues fetching original content from Vault.")
        sys.exit(0)

    with open(patch_filename, 'w', encoding='utf-8') as f:
        f.writelines(all_diffs)
        
    logging.info(f"Successfully created patch file: {patch_filename}")
