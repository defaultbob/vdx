import xml.dom.minidom
import re
import hashlib
import json
import os
import logging
import fnmatch
from pathlib import Path

try:
    from vdx.version import VERSION
except ImportError:
    VERSION = "0.0.0"

STATE_FILE = ".vdx_state.json"
IGNORE_FILE = ".vdxignore"

def compute_checksum(content):
    if content is None:
        return ""
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.md5(content).hexdigest()

def load_ignore_patterns():
    # We look for .vdxignore in the current working directory where the user runs the command
    if os.path.exists(IGNORE_FILE):
        with open(IGNORE_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    return []

def is_ignored(file_path, patterns):
    for pattern in patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                state_version = state.get("__vdx_version__", "0.0.0")
                if state_version != VERSION:
                    logging.info(f"VDX upgraded ({state_version} -> {VERSION}). Invalidating local state to force a clean pull.")
                    # Keep the pull mode preference if it exists when invalidating
                    return {"__pull_mode__": state.get("__pull_mode__", "simple")}
                return state
        except Exception:
            return {}
    return {}

def save_state(state):
    state["__vdx_version__"] = VERSION
    # Ensure a pull mode is always set
    if "__pull_mode__" not in state:
        state["__pull_mode__"] = "simple"
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=4)

def sort_json_obj(obj):
    """
    Recursively sorts JSON objects to ensure deterministic output for version control.
    Dictionaries are sorted by their keys (when dumped with sort_keys=True).
    Lists of primitives or dictionaries with 'name' are sorted accordingly.
    """
    if isinstance(obj, dict):
        return {k: sort_json_obj(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        sorted_list = [sort_json_obj(item) for item in obj]
        try:
            # If it's a list of dicts with 'name', sort by 'name'
            if all(isinstance(i, dict) and 'name' in i for i in sorted_list):
                return sorted(sorted_list, key=lambda x: x['name'])
            # For lists of primitives (strings, ints), sort normally
            return sorted(sorted_list, key=lambda x: json.dumps(x, sort_keys=True))
        except Exception:
            # Fallback to unsorted if elements are heterogeneous or uncomparable
            return sorted_list
    return obj

def load_dotenv(filepath=".env"):
    # Check current directory for .env
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    val = val.strip().strip('\'"')
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = val

def format_mdl(mdl_str):
    if not mdl_str or '\n' in mdl_str.strip():
        return mdl_str
    
    first_paren = mdl_str.find('(')
    last_paren = mdl_str.rfind(')')
    if first_paren == -1 or last_paren == -1 or first_paren >= last_paren:
        return mdl_str
        
    header = mdl_str[:first_paren]
    content = mdl_str[first_paren+1:last_paren]
    footer = mdl_str[last_paren+1:]
    
    attrs = []
    current_attr = []
    depth = 0
    in_quotes = False
    quote_char = ''
    
    for char in content:
        if in_quotes:
            current_attr.append(char)
            if char == quote_char:
                in_quotes = False
        else:
            if char in ["'", '"']:
                in_quotes = True
                quote_char = char
                current_attr.append(char)
            elif char == '(':
                depth += 1
                current_attr.append(char)
            elif char == ')':
                depth -= 1
                current_attr.append(char)
            elif char == ',' and depth == 0:
                attrs.append("".join(current_attr).strip())
                current_attr = []
            else:
                current_attr.append(char)
    if current_attr:
        attrs.append("".join(current_attr).strip())
        
    formatted_attrs = ",\n   ".join(attrs)
    return f"{header}(\n   {formatted_attrs}\n){footer}"



def format_action_script(as_str):
    lines = as_str.splitlines()
    formatted_lines = []
    indent_level = 0
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
            
        # Check if line contains a closing brace
        if stripped.startswith('}'):
            indent_level = max(0, indent_level - 1)
            
        if stripped.upper() in ["IF", "THEN", "ELSE"]:
            # Keywords are flush left
            formatted_lines.append(stripped)
        else:
            indent_str = "    " * (indent_level + 1)
            formatted_lines.append(indent_str + stripped)
            
        # Check if line ends with an opening brace
        if stripped.endswith('{'):
            indent_level += 1

    return "\n".join(formatted_lines)

def process_mdl_and_extract(mdl_str, metadata_json, comp_type, comp_name, base_dir="components", comp_class_map=None):
    """
    Parses MDL, formats it properly, extracts specified values into external files.
    Returns (formatted_mdl, dict_of_extracted_files)
    """
    if comp_class_map is None:
        comp_class_map = {}

    attributes_metadata = {}
    if metadata_json and "data" in metadata_json:
        data_obj = metadata_json["data"]
        if isinstance(data_obj, dict):
            for attr in data_obj.get("attributes", []):
                if isinstance(attr, dict):
                    attributes_metadata[attr.get("name")] = attr
            for sc in data_obj.get("sub_components", []):
                for attr in sc.get("attributes", []):
                    if isinstance(attr, dict):
                        attributes_metadata[attr.get("name")] = attr
            
    extracted_files = {}

    INC_OVERRIDES = ["email_body", "notification", "subject", "help_content"]
    JSON_OVERRIDES = ["conditions", "trigger_date"]
    JS_OVERRIDES = ["validator_code"]

    def get_extraction_info(c_type, attr_name, val):
        meta = attributes_metadata.get(attr_name, {})
        data_type = meta.get("type", "")
        
        ext = None
        content_to_save = val
        
        if data_type == "XMLString":
            ext = ".xml"
        elif data_type == "JSONString":
            ext = ".json"
            
        if attr_name in INC_OVERRIDES:
            ext = ".inc"
        elif attr_name in JSON_OVERRIDES:
            ext = ".json"
        elif attr_name in JS_OVERRIDES:
            ext = ".js"
            
        if "<ActionScript>" in val and "</ActionScript>" in val:
            ext = ".as"
            val_clean = val.replace("<ActionScript>", "").replace("</ActionScript>", "").strip()
            content_to_save = format_action_script(val_clean)
            
        if ext == ".xml":
            val_clean = val.strip()
            if val_clean.startswith("{") and val_clean.endswith("}"): val_clean = val_clean[1:-1]
            elif val_clean.startswith("'") and val_clean.endswith("'"): val_clean = val_clean[1:-1]
            elif val_clean.startswith('"') and val_clean.endswith('"'): val_clean = val_clean[1:-1]
            
            try:
                parsed_xml = xml.dom.minidom.parseString(val_clean.encode("utf-8"))
                for child in parsed_xml.childNodes:
                    if child.nodeType == xml.dom.minidom.Node.PROCESSING_INSTRUCTION_NODE or (child.nodeType == xml.dom.Node.DOCUMENT_NODE and not child.documentElement):
                         pass
                pretty_xml = parsed_xml.toprettyxml(indent="    ")
                xml_lines = [line for line in pretty_xml.splitlines() if line.strip() and not line.strip().startswith("<?xml")]
                content_to_save = "\n".join(xml_lines)
            except Exception as e:
                content_to_save = val_clean
                
        elif ext == ".json":
            val_clean = val.strip()
            if val_clean.startswith("{") and val_clean.endswith("}"): pass
            elif val_clean.startswith("'") and val_clean.endswith("'"): val_clean = val_clean[1:-1]
            elif val_clean.startswith('"') and val_clean.endswith('"'): val_clean = val_clean[1:-1]
            try:
                parsed_json = json.loads(val_clean)
                content_to_save = json.dumps(parsed_json, indent=4)
            except Exception:
                content_to_save = val_clean
                
        elif ext in (".inc", ".js"):
            val_clean = val.strip()
            if val_clean.startswith("'") and val_clean.endswith("'"): val_clean = val_clean[1:-1]
            elif val_clean.startswith('"') and val_clean.endswith('"'): val_clean = val_clean[1:-1]
            content_to_save = val_clean

        return ext, content_to_save
        
    def format_block(content, block_c_type, block_c_name, current_dir, is_top_level=False):
        attrs = []
        current_attr = []
        depth = 0
        in_quotes = False
        quote_char = ''
        
        items = []
        for char in content:
            if in_quotes:
                current_attr.append(char)
                if char == quote_char:
                    in_quotes = False
            else:
                if char in ["'", '"']:
                    in_quotes = True
                    quote_char = char
                    current_attr.append(char)
                elif char == '(':
                    depth += 1
                    current_attr.append(char)
                elif char == ')':
                    depth -= 1
                    current_attr.append(char)
                elif char == ',' and depth == 0:
                    items.append("".join(current_attr).strip())
                    current_attr = []
                else:
                    current_attr.append(char)
        if current_attr:
            items.append("".join(current_attr).strip())

        formatted_items = []
        for item in items:
            sub_match = re.match(r'^([A-Z][a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)\s*\((.*)\)$', item, re.DOTALL)
            if sub_match:
                s_type = sub_match.group(1)
                s_name = sub_match.group(2)
                s_content = sub_match.group(3)
                
                sub_dir = os.path.join(current_dir, s_type, s_name)
                f_sub_content = format_block(s_content, s_type, s_name, sub_dir, is_top_level=False)
                
                sub_mdl = f"{s_type} {s_name}(\n   {f_sub_content}\n)"
                extracted_files[os.path.join(sub_dir, f"{s_name}.mdl")] = sub_mdl
                formatted_items.append(f'<INCLUDES {s_type}/{s_name}/{s_name}.mdl>')
            else:
                attr_match = re.match(r'^([a-zA-Z0-9_]+)\s*\((.*)\)$', item, re.DOTALL)
                if attr_match:
                    a_name = attr_match.group(1)
                    a_val = attr_match.group(2)
                    
                    if a_val:
                        # 1. Check if it's a code component reference
                        meta = attributes_metadata.get(a_name, {})
                        if meta.get("type") == "ComponentReference":
                            ref_type = meta.get("component")
                            if comp_class_map.get(ref_type) == "code":
                                name = a_val.strip("'\"")
                                if name.startswith(ref_type + "."):
                                    name = name[len(ref_type)+1:]
                                
                                if name.startswith("com.veeva.vault.custom."):
                                    package_path = name.rsplit('.', 1)[0].replace('.', os.path.sep)
                                    levels = len(Path(current_dir).parts)
                                    rel_root = (".." + os.path.sep) * levels
                                    java_path = os.path.join(rel_root, "javasdk", package_path, f"{name}.java")
                                    formatted_items.append(f'{a_name}(<INCLUDES {java_path}>)')
                                    continue

                        ext, content_to_save = get_extraction_info(block_c_type, a_name, a_val)
                        if ext:
                            filename = f"{a_name}{ext}"
                            file_path = os.path.join(current_dir, filename)
                            extracted_files[file_path] = content_to_save
                            formatted_items.append(f'{a_name}(<INCLUDES {filename}>)')
                        else:
                            formatted_items.append(item)
                    else:
                        formatted_items.append(item)
                else:
                    formatted_items.append(item)
                    
        return (",\n   ").join(formatted_items)

    if not mdl_str:
        return {}
        
    mdl_str = mdl_str.strip()
    first_paren = mdl_str.find('(')
    last_paren = mdl_str.rfind(')')
    if first_paren == -1 or last_paren == -1 or first_paren >= last_paren:
        return {}
        
    header = mdl_str[:first_paren].strip()
    content = mdl_str[first_paren+1:last_paren]
    footer = mdl_str[last_paren+1:].strip()
    
    comp_dir = os.path.join(base_dir, comp_type, comp_name)
    formatted_content = format_block(content, comp_type, comp_name, comp_dir, is_top_level=True)
    
    final_mdl = f"{header} (\n   {formatted_content}\n){footer}"
    extracted_files[os.path.join(comp_dir, f"{comp_name}.mdl")] = final_mdl
    
    return extracted_files


def reassemble_component(base_dir, comp_type, comp_name):
    comp_dir = os.path.join(base_dir, comp_type, comp_name)
    root_mdl_path = os.path.join(comp_dir, f"{comp_name}.mdl")
    
    # If the root component is a simple file (i.e., not a directory structure)
    if not os.path.isdir(comp_dir):
        # Fallback to simple mode: components/Type/Name.mdl or components/Type/Name/Name.mdl
        simple_path = os.path.join(base_dir, comp_type, f"{comp_name}.mdl")
        if os.path.exists(simple_path):
            with open(simple_path, 'r', encoding='utf-8') as f:
                return f.read()
        return None
        
    if not os.path.exists(root_mdl_path):
        return None
        
    def _reassemble_recursive(current_dir, mdl_file_name, is_root=False):
        mdl_path = os.path.join(current_dir, mdl_file_name)
        if not os.path.exists(mdl_path):
            return ""
            
        with open(mdl_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        def pointer_replacer(match):
            attr_name = match.group(1)
            filename = match.group(2)
            pointer_path = os.path.join(current_dir, filename)
            
            # Handle .java pointers by reconstructing Type.Name
            if filename.endswith(".java"):
                # 1. Get the component name from the filename
                basename = os.path.basename(filename)
                comp_name_ref = basename.replace(".java", "")
                
                # 2. Find the component type from metadata
                # We need to find the metadata for the block we are currently in
                # Let's try to find metadata.json in parent folders
                ref_type = ""
                search_dir = current_dir
                while search_dir and search_dir != base_dir:
                    meta_path = os.path.join(search_dir, "metadata.json")
                    if os.path.exists(meta_path):
                        try:
                            with open(meta_path, 'r') as mf:
                                meta_data = json.load(mf)
                                # Find attribute in metadata
                                # This handles both top-level and sub-component attributes
                                attributes = []
                                d = meta_data.get("data", {})
                                if isinstance(d, dict):
                                    attributes.extend(d.get("attributes", []))
                                    for sc in d.get("sub_components", []):
                                        attributes.extend(sc.get("attributes", []))
                                
                                for attr in attributes:
                                    if attr.get("name") == attr_name:
                                        ref_type = attr.get("component", "")
                                        break
                        except Exception:
                            pass
                    if ref_type:
                        break
                    # Move up
                    new_search_dir = os.path.dirname(search_dir)
                    if new_search_dir == search_dir: break
                    search_dir = new_search_dir
                
                if ref_type:
                    return f"{attr_name}('{ref_type}.{comp_name_ref}')"
                else:
                    # Fallback to just Name if type not found
                    return f"{attr_name}('{comp_name_ref}')"

            if os.path.exists(pointer_path):
                with open(pointer_path, 'r', encoding='utf-8') as pf:
                    ptr_content = pf.read().strip()
                
                if filename.endswith(".xml"):
                    return f"{attr_name}({{{ptr_content}}})"
                elif filename.endswith(".json") or filename.endswith(".inc"):
                    escaped_content = ptr_content.replace("'", "''")
                    return f"{attr_name}('{escaped_content}')"
                elif filename.endswith(".as"):
                    return f"{attr_name}(<ActionScript>\n{ptr_content}\n</ActionScript>)"
                else:
                    return f"{attr_name}('{ptr_content}')"
            return match.group(0) # fallback
            
        content = re.sub(r'([a-zA-Z0-9_]+)\(<INCLUDES\s+((?:[^>\\]|\\.)+)>\)', pointer_replacer, content)
        content = re.sub(r',?\s*<INCLUDES\s+(?:[^>\\]|\\.)+>', '', content)

        subcomponents = []
        for item in os.listdir(current_dir):
            item_path = os.path.join(current_dir, item)
            if os.path.isdir(item_path) and item[0].isupper():
                sub_type = item
                for sub_name in os.listdir(item_path):
                    sub_comp_dir = os.path.join(item_path, sub_name)
                    if os.path.isdir(sub_comp_dir):
                        sub_content = _reassemble_recursive(sub_comp_dir, f"{sub_name}.mdl", is_root=False)
                        if sub_content:
                            # Indent sub_content properly (since we append it inside the parent)
                            indented = "\n".join(["   " + line if line.strip() else line for line in sub_content.splitlines()])
                            subcomponents.append(indented)
                            
        if subcomponents:
            last_paren_idx = content.rfind(')')
            if last_paren_idx != -1:
                before_paren = content[:last_paren_idx].rstrip()
                prefix = ""
                if not before_paren.endswith('('):
                    prefix = ","
                
                subs_str = ",\n".join(subcomponents)
                content = content[:last_paren_idx] + prefix + "\n" + subs_str + "\n" + content[last_paren_idx:]
                
        return content

    return _reassemble_recursive(comp_dir, f"{comp_name}.mdl", is_root=True)

