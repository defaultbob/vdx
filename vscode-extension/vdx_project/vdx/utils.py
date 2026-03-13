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
                    return {}
                return state
        except Exception:
            return {}
    return {}

def save_state(state):
    state["__vdx_version__"] = VERSION
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
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.upper() in ["IF", "THEN", "ELSE"]:
            formatted_lines.append(stripped)
        else:
            formatted_lines.append("    " + stripped)
    return "\n".join(formatted_lines)

def process_mdl_and_extract(mdl_str, metadata_json, comp_type, comp_name, base_dir="components"):
    """
    Parses MDL, formats it properly, extracts specified values into external files.
    Returns (formatted_mdl, dict_of_extracted_files)
    """
    # Quick fix to get metadata attributes
    attributes_metadata = {}
    if metadata_json and "data" in metadata_json:
        data_obj = metadata_json["data"]
        # In component metadata, "data" is an object that contains an "attributes" array
        if isinstance(data_obj, dict) and "attributes" in data_obj:
            for attr in data_obj["attributes"]:
                if isinstance(attr, dict):
                    attributes_metadata[attr.get("name")] = attr
            
    extracted_files = {}

    # Overrides defined by the user
    HTML_OVERRIDES = ["email_body", "notification", "subject", "help_content"]
    JSON_OVERRIDES = ["context_configuration", "conditions", "trigger_date", "layout_markup", "properties", "step_detail", "configuration"]

    # Helper to determine extraction info
    def get_extraction_info(c_type, attr_name, val):
        meta = attributes_metadata.get(attr_name, {})
        data_type = meta.get("type", "")
        
        ext = None
        content_to_save = val
        
        # 1. Native XMLString or JSONString
        if data_type == "XMLString":
            ext = ".xml"
        elif data_type == "JSONString":
            ext = ".json"
            
        # 2. Overrides
        if attr_name in HTML_OVERRIDES:
            ext = ".html"
        elif attr_name in JSON_OVERRIDES:
            ext = ".json"
            
        # 3. ActionScript
        if "<ActionScript>" in val and "</ActionScript>" in val:
            ext = ".as"
            val_clean = val.replace("<ActionScript>", "").replace("</ActionScript>", "").strip()
            content_to_save = format_action_script(val_clean)
            
        # Format XML/JSON if not ActionScript
        if ext == ".xml":
            # Remove wrappers if any (like {<...>} or '<...>')
            val_clean = val.strip()
            if val_clean.startswith("{") and val_clean.endswith("}"):
                val_clean = val_clean[1:-1]
            elif val_clean.startswith("'") and val_clean.endswith("'"):
                val_clean = val_clean[1:-1]
            elif val_clean.startswith('"') and val_clean.endswith('"'):
                val_clean = val_clean[1:-1]
            
            try:
                # Strip out encoding string when parsing XML (xml.dom.minidom might add it back, we can replace it)
                parsed_xml = xml.dom.minidom.parseString(val_clean.encode("utf-8"))
                # Remove XML declaration
                for child in parsed_xml.childNodes:
                    if child.nodeType == xml.dom.minidom.Node.PROCESSING_INSTRUCTION_NODE or (child.nodeType == xml.dom.Node.DOCUMENT_NODE and not child.documentElement):
                         pass
                
                pretty_xml = parsed_xml.toprettyxml(indent="    ")
                # Remove empty lines and <?xml ...?>
                xml_lines = [line for line in pretty_xml.splitlines() if line.strip() and not line.strip().startswith("<?xml")]
                content_to_save = "\n".join(xml_lines)
            except Exception as e:
                content_to_save = val_clean
                
        elif ext == ".json":
            val_clean = val.strip()
            if val_clean.startswith("{") and val_clean.endswith("}"):
                pass # keep braces
            elif val_clean.startswith("'") and val_clean.endswith("'"):
                val_clean = val_clean[1:-1]
            elif val_clean.startswith('"') and val_clean.endswith('"'):
                val_clean = val_clean[1:-1]
                
            # Unescape if it was stringified JSON
            try:
                parsed_json = json.loads(val_clean)
                content_to_save = json.dumps(parsed_json, indent=4)
            except Exception:
                content_to_save = val_clean
                
        elif ext == ".html":
            val_clean = val.strip()
            if val_clean.startswith("'") and val_clean.endswith("'"):
                val_clean = val_clean[1:-1]
            elif val_clean.startswith('"') and val_clean.endswith('"'):
                val_clean = val_clean[1:-1]
            content_to_save = val_clean
            
        return ext, content_to_save
        
    # Formatting logic that recurses
    def format_block(content, block_c_type, block_c_name, depth_indent=""):
        attrs = []
        current_attr = []
        depth = 0
        in_quotes = False
        quote_char = ''
        
        # Split content into top-level items by comma
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
            # Check if it's a sub-component vs an attribute
            # A sub-component looks like `SubCompType sub_comp_name(...)`
            sub_match = re.match(r'^([A-Z][a-zA-Z0-9_]+)\s+([a-zA-Z0-9_]+)\s*\((.*)\)$', item, re.DOTALL)
            if sub_match:
                s_type = sub_match.group(1)
                s_name = sub_match.group(2)
                s_content = sub_match.group(3)
                
                f_sub_content = format_block(s_content, s_type, s_name, depth_indent + "   ")
                formatted_items.append(f"{s_type} {s_name}(\n{depth_indent}      {f_sub_content}\n{depth_indent}   )")
            else:
                # It's an attribute
                attr_match = re.match(r'^([a-zA-Z0-9_]+)\s*\((.*)\)$', item, re.DOTALL)
                if attr_match:
                    a_name = attr_match.group(1)
                    a_val = attr_match.group(2)
                    
                    if a_val:
                        ext, content_to_save = get_extraction_info(block_c_type, a_name, a_val)
                        if ext:
                            filename = f"{block_c_type}.{block_c_name}.{a_name}{ext}"
                            file_path = os.path.join(base_dir, block_c_type, filename)
                            extracted_files[file_path] = content_to_save
                            
                            # Replace attribute value with pointer
                            formatted_items.append(f"{a_name}('{filename}')")
                        else:
                            formatted_items.append(item)
                    else:
                        formatted_items.append(item)
                else:
                    formatted_items.append(item)
                    
        return (",\n" + depth_indent + "   ").join(formatted_items)


    if not mdl_str:
        return mdl_str, extracted_files
        
    mdl_str = mdl_str.strip()
    first_paren = mdl_str.find('(')
    last_paren = mdl_str.rfind(')')
    if first_paren == -1 or last_paren == -1 or first_paren >= last_paren:
        return mdl_str, extracted_files
        
    header = mdl_str[:first_paren].strip()
    content = mdl_str[first_paren+1:last_paren]
    footer = mdl_str[last_paren+1:].strip()
    
    formatted_content = format_block(content, comp_type, comp_name, "")
    
    final_mdl = f"{header} (\n   {formatted_content}\n){footer}"
    return final_mdl, extracted_files

