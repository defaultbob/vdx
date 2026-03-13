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

## Attribute Extraction & Overrides

Certain attributes contain complex structures (XML, JSON, HTML, ActionScript) that must be extracted to separate files to ensure proper version control and developer experience. The `vdx.utils.process_mdl_and_extract` parser handles this dynamically by reading the `METADATA-*.json` definition for the component and applying specific overrides.

### 1. Native Metadata Types
- Any attribute defined with `type: "XMLString"` in the Vault metadata is extracted to a `.xml` file. The parser strips any `<?xml ... ?>` encoding declarations.
- Any attribute defined with `type: "JSONString"` in the Vault metadata is extracted to a `.json` file and formatted with standard 4-space indentation.

### 2. Known Type Overrides
Some attributes are defined as generic `String` in the metadata but actually contain structured formats. The parser forcefully overrides these:

**HTML Overrides (Extracted to `.html`)**
- `email_body`
- `notification`
- `subject`
- `help_content`

**JSON Overrides (Extracted to `.json`)**
- `context_configuration`
- `conditions`
- `trigger_date`
- `layout_markup`
- `properties`
- `step_detail`
- `configuration`

### 3. ActionScript Processing
If an attribute's value contains the `<ActionScript>` tag, it is extracted to a `.as` file.
- The `<ActionScript>` and `</ActionScript>` tags are removed.
- Line endings are preserved.
- All lines are indented with 4 spaces, EXCEPT the keywords `IF`, `THEN`, and `ELSE`, which must remain unindented (flush left).