import os
import re

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
            if os.path.exists(pointer_path):
                with open(pointer_path, 'r', encoding='utf-8') as pf:
                    ptr_content = pf.read().strip()
                
                if filename.endswith(".xml"):
                    return f"{attr_name}({{{ptr_content}}})"
                elif filename.endswith(".json"):
                    # Unescape for JSONString or just wrap in single quotes? 
                    # If it's pure JSON, it was dumped with indent=4, so it spans multiple lines. 
                    # Wait, in the pull script, we stripped quotes. We should wrap it back in single quotes.
                    # Vault expects JSON strings to have escaped inner quotes or be wrapped in single quotes
                    # Actually, replacing newlines or just returning the block in quotes is usually enough.
                    # But the easiest is just what Vault generated originally.
                    # If we use single quotes for the outer wrapper, we have to escape inner single quotes.
                    # Let's just wrap it in single quotes. If there are single quotes inside the json, 
                    # they might break it. But pull.py stripped the outer quotes so we must add them back.
                    escaped_content = ptr_content.replace("'", "''")
                    return f"{attr_name}('{escaped_content}')"
                elif filename.endswith(".html"):
                    escaped_content = ptr_content.replace("'", "''")
                    return f"{attr_name}('{escaped_content}')"
                elif filename.endswith(".as"):
                    return f"{attr_name}(<ActionScript>\n{ptr_content}\n</ActionScript>)"
                else:
                    return f"{attr_name}('{ptr_content}')"
            return match.group(0) # fallback
            
        content = re.sub(r"([a-zA-Z0-9_]+)\(\s*\{([^}]+)\}\s*\)", pointer_replacer, content)
        
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

# Generate some dummy data to test
os.makedirs("components/Object/my_object__c/Field/my_field__c", exist_ok=True)
with open("components/Object/my_object__c/my_object__c.mdl", "w") as f:
    f.write("RECREATE Object my_object__c (\n   label('My Object'),\n   active(false)\n);")
with open("components/Object/my_object__c/Field/my_field__c/my_field__c.mdl", "w") as f:
    f.write("Field my_field__c(\n   label('My Field'),\n   help_content({help_content.html})\n)")
with open("components/Object/my_object__c/Field/my_field__c/help_content.html", "w") as f:
    f.write("<b>Some HTML with 'single quotes'</b>")

print(reassemble_component("components", "Object", "my_object__c"))
