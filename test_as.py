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

test_script = """IF
total_amount__c >= 1000000
THEN
{
SendNotification($big_order__c, UserNames("david.mills@veeva.com"));
UpdateRecord();
}"""

print(format_action_script(test_script))
