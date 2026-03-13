import os
with open('vdx_project/vdx/utils.py', 'r') as f:
    content = f.read()

# Remove the old format_mdl
import re
content = re.sub(r'def format_mdl\(mdl_str\):.*?return f"\{header\}\(\n   \{formatted_attrs\}\n\)\{footer\}"\n', '', content, flags=re.DOTALL)

with open('test_mdl_parser.py', 'r') as f:
    parser_code = f.read()

# Get only the function definitions
functions_to_add = parser_code.split('if __name__ == "__main__":')[0]
# remove imports at top since we already have them or will add them
functions_to_add = functions_to_add.replace("import re\nimport json\nimport xml.dom.minidom\nimport os\n", "")

with open('vdx_project/vdx/utils.py', 'w') as f:
    f.write("import xml.dom.minidom\nimport re\n" + content + "\n" + functions_to_add)
