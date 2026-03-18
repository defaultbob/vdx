import logging
import os
import re
from vdx.utils import process_mdl_and_extract

def split_mdl_components(mdl_str):
    components = []
    current_comp = []
    depth = 0
    in_string = False
    string_char = ''
    
    # Simple state machine to split on top-level semicolons
    for char in mdl_str:
        if not in_string:
            if char in ("'", '"'):
                in_string = True
                string_char = char
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
        else:
            if char == string_char:
                # Need to handle escaping if we want to be perfectly robust, 
                # but Vault MDL usually doesn't escape quotes like \", it uses the other quote
                in_string = False
                
        current_comp.append(char)
        
        # Semicolon at depth 0 means end of a top level component
        if depth == 0 and char == ';' and not in_string:
            comp_text = "".join(current_comp).strip()
            if comp_text:
                components.append(comp_text)
            current_comp = []

    # Catch any trailing content without a semicolon
    leftover = "".join(current_comp).strip()
    if leftover:
        components.append(leftover)
        
    return components

def run_organize(args):
    target_file = args.file
    if not os.path.exists(target_file):
        logging.error(f"File not found: {target_file}")
        return

    with open(target_file, 'r', encoding='utf-8') as f:
        mdl_str = f.read()

    components = split_mdl_components(mdl_str)
    
    if not components:
        logging.info("No components found to organize.")
        return

    logging.info(f"Found {len(components)} component(s) to organize.")

    for comp_str in components:
        # Parse root component type and name
        # e.g., RECREATE Object my_object__c (
        match = re.search(r'^\s*(?:(?:RECREATE|CREATE|ALTER|DROP)\s+)?([A-Z][a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)\s*\(', comp_str)
        if not match:
            logging.warning(f"Could not parse root component type and name from block:\n{comp_str[:100]}...")
            continue

        comp_type = match.group(1)
        comp_name = match.group(2)

        logging.info(f"Organizing component: {comp_type} {comp_name}")

        extracted_files = process_mdl_and_extract(comp_str, {}, comp_type, comp_name, base_dir="components")
        
        for file_path, content in extracted_files.items():
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logging.info(f"Wrote {file_path}")

    logging.info("Organization complete.")