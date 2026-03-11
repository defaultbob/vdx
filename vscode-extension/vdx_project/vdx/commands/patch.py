import os
import sys
import logging
import difflib
from pathlib import Path
import json
import tempfile

from vdx.api import make_vault_request, API_VERSION
from vdx.utils import load_state, compute_checksum

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
            return data["data"][0].get("mdl_definition__v", "")
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
    
    modified_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".mdl"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                current_checksum = compute_checksum(content)
                if state.get(file_path) != current_checksum:
                    modified_files.append((file_path, content))

    if not modified_files:
        if args.json:
            print("[]")
        else:
            logging.info("No modified components found.")
        sys.exit(0)

    if args.json:
        json_output = []
        for file_path, current_content in modified_files:
            path_parts = Path(file_path).parts
            comp_type = path_parts[-2]
            comp_name = path_parts[-1].replace(".mdl", "")
            
            original_content = get_vault_mdl_content(comp_type, comp_name)
            
            if original_content is not None:
                with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8', suffix=".mdl") as tmp:
                    tmp.write(original_content)
                    original_file_path = tmp.name
                
                json_output.append({
                    "file_path": file_path,
                    "original_file": original_file_path,
                    "modified_file": os.path.abspath(file_path)
                })
        print(json.dumps(json_output, indent=2))
        sys.exit(0)


    logging.info(f"Found {len(modified_files)} modified components. Generating patch...")

    all_diffs = []
    for file_path, current_content in modified_files:
        path_parts = Path(file_path).parts
        comp_type = path_parts[-2]
        comp_name = path_parts[-1].replace(".mdl", "")
        
        original_content = get_vault_mdl_content(comp_type, comp_name)
        
        if original_content is not None:
            diff = difflib.unified_diff(
                original_content.splitlines(keepends=True),
                current_content.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
            all_diffs.extend(list(diff))

    if not all_diffs:
        logging.info("Could not generate diffs for modified files. This might be due to issues fetching original content from Vault.")
        sys.exit(0)

    with open(patch_filename, 'w', encoding='utf-8') as f:
        f.writelines(all_diffs)
        
    logging.info(f"Successfully created patch file: {patch_filename}")
    logging.info(f"Found {len(modified_files)} modified components. Generating patch...")

    all_diffs = []
    for file_path, current_content in modified_files:
        path_parts = Path(file_path).parts
        comp_type = path_parts[-2]
        comp_name = path_parts[-1].replace(".mdl", "")
        
        original_content = get_vault_mdl_content(comp_type, comp_name)
        
        if original_content is not None:
            diff = difflib.unified_diff(
                original_content.splitlines(keepends=True),
                current_content.splitlines(keepends=True),
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
            )
            all_diffs.extend(list(diff))

    if not all_diffs:
        logging.info("Could not generate diffs for modified files. This might be due to issues fetching original content from Vault.")
        sys.exit(0)

    with open(patch_filename, 'w', encoding='utf-8') as f:
        f.writelines(all_diffs)
        
    logging.info(f"Successfully created patch file: {patch_filename}")
