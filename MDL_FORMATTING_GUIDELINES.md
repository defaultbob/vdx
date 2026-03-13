# MDL Formatting Guidelines

This document serves as the machine-readable specification for generating and formatting Veeva Vault MDL (Metadata Definition Language) components within the `vdx` project.

## General Structure

All top-level MDL components follow this structural pattern:

```mdl
<COMMAND> <ComponentType> <component_name> (
   <attribute_1>(<value>),
   <attribute_2>(<value>),
   <attribute_3>(<value>)
);
```

### Specific Formatting Rules

1. **Header:** The command (e.g., `RECREATE`), the component type, and the component name should appear on the first line, followed by a space and an opening parenthesis `(`.
2. **Attributes:**
   - Every attribute MUST be placed on its own line.
   - Every attribute line MUST be indented with exactly three (3) spaces.
   - Attributes are comma-separated. The comma MUST be placed at the end of the line immediately following the closing parenthesis of the attribute's value (e.g., `),`).
   - The final attribute in the list does NOT contain a trailing comma.
3. **Closing/Footer:**
   - The closing parenthesis `)` MUST be placed on a new line.
   - The closing parenthesis MUST NOT be indented (it must align with the first character of the Header).
   - A trailing semicolon `;` MUST immediately follow the closing parenthesis (e.g., `);`).

## Parser Implementation Details

When parsing and formatting raw or single-line MDL strings (e.g., within `vdx.utils.format_mdl`):
- String values containing parentheses or commas inside quotes (single `'` or double `"`) MUST NOT be split.
- Nested parentheses (e.g., when an attribute's value contains a function or nested definition) MUST be tracked using depth-counting to avoid splitting mid-attribute. 
- Empty attributes (e.g., `description()`) should be treated identically to populated attributes.