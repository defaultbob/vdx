import re
import json
import os
import xml.dom.minidom

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
    attributes_metadata = {}
    if metadata_json and "data" in metadata_json:
        data_obj = metadata_json["data"]
        if isinstance(data_obj, dict) and "attributes" in data_obj:
            for attr in data_obj["attributes"]:
                if isinstance(attr, dict):
                    attributes_metadata[attr.get("name")] = attr
            
    extracted_files = {}

    HTML_OVERRIDES = ["email_body", "notification", "subject", "help_content"]
    JSON_OVERRIDES = ["context_configuration", "conditions", "trigger_date", "layout_markup", "properties", "step_detail", "configuration"]

    def get_extraction_info(c_type, attr_name, val):
        meta = attributes_metadata.get(attr_name, {})
        data_type = meta.get("type", "")
        
        ext = None
        content_to_save = val
        
        if data_type == "XMLString":
            ext = ".xml"
        elif data_type == "JSONString":
            ext = ".json"
            
        if attr_name in HTML_OVERRIDES:
            ext = ".html"
        elif attr_name in JSON_OVERRIDES:
            ext = ".json"
            
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
                
        elif ext == ".html":
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
                # Do NOT append to formatted_items, so it's stripped from parent
            else:
                attr_match = re.match(r'^([a-zA-Z0-9_]+)\s*\((.*)\)$', item, re.DOTALL)
                if attr_match:
                    a_name = attr_match.group(1)
                    a_val = attr_match.group(2)
                    
                    if a_val:
                        ext, content_to_save = get_extraction_info(block_c_type, a_name, a_val)
                        if ext:
                            filename = f"{a_name}{ext}"
                            file_path = os.path.join(current_dir, filename)
                            extracted_files[file_path] = content_to_save
                            
                            # Replace attribute value with pointer {filename}
                            formatted_items.append(f"{a_name}({{{filename}}})")
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

if __name__ == "__main__":
    test_mdl = '''RECREATE Object my_object__c (
   label('My Object'),
   active(false),
   Field my_field__c(
      label('My Field'),
      type('String'),
      help_content('<b>Some HTML</b>')
   )
);'''
    files = process_mdl_and_extract(test_mdl, {}, "Object", "my_object__c")
    for k, v in files.items():
        print(f"--- {k} ---")
        print(v)

