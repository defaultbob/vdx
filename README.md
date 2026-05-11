# vdx — Vault Developer eXperience

**vdx** is a CLI tool that syncs Veeva Vault configuration to local files for source control, code review, and deployment. It speaks the Vault API and MDL (Metadata Definition Language), pulling vault components down into a structured directory tree and pushing changes back up.

---

## Installation

```bash
git clone <repo-url>
cd vdx
python3 -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate
pip install requests

# Make vdx available globally (Mac/Linux)
chmod +x vdx_project/main.py
sudo ln -s "$(pwd)/vdx_project/main.py" /usr/local/bin/vdx
```

**Windows (PowerShell profile):**
```powershell
function vdx { & "C:\path\to\vdx\venv\Scripts\python.exe" "C:\path\to\vdx\vdx_project\main.py" $args }
```

### VS Code Extension

Install `vdx-vscode-x.x.x.vsix` from the `vscode-extension/` directory via _Extensions → Install from VSIX_.

---

## Configuration

Create a `.env` file in your working directory:

```bash
VAULT_DNS="your-vault.veevavault.com"
VAULT_USERNAME="your.email@company.com"
VAULT_PASSWORD="your_password"
```

Optionally add a `.vdxignore` file using glob patterns to skip components:

```
components/Picklist/*__sys
components/Group/system_*
```

---

## Commands

| Command | Description |
|---|---|
| `vdx login` | Authenticate and store a session |
| `vdx pull` | Pull all components from Vault |
| `vdx pull --simple` | Pull as monolithic MDL files (no extraction) |
| `vdx pull --translations` | Also pull bulk translation CSVs |
| `vdx push` | Push local changes to Vault |
| `vdx push --dry-run` | Preview changes without deploying |
| `vdx push --file <path>` | Push a single file (and its parent component) |
| `vdx push --translations` | Also push translations |
| `vdx organize <file.mdl>` | Explode a raw MDL file into the directory structure |
| `vdx package` | Build a VPK and trigger validation in Vault |
| `vdx patch` | Generate a patch file of local changes |
| `vdx clean-cache` | Remove `.vdx_config` and `.vdx_state.json` |
| `vdx clean-files` | Delete all pulled files and cache |

---

## Directory Structure (Advanced Mode)

Advanced mode is the default. It extracts subcomponents and large attribute values into separate files for clean diffs and code review.

```
<working-directory>/
│
├── components/                         # Vault metadata components
│   └── <ComponentType>/
│       ├── metadata.json               # Type-level API metadata
│       └── <component_name>/
│           ├── <component_name>.mdl    # Root MDL file (see format below)
│           └── <SubType>/
│               └── <sub_name>/
│                   ├── <sub_name>.mdl  # Subcomponent MDL
│                   ├── *.xml           # Extracted XML attributes
│                   ├── *.json          # Extracted JSON attributes
│                   ├── *.inc           # Extracted HTML/template attributes
│                   ├── *.as            # Extracted ActionScript attributes
│                   └── *.js            # Extracted JavaScript attributes
│
├── javasdk/                            # Vault SDK code components
│   └── com/veeva/vault/custom/
│       └── <package>/<ClassName>.java
│
├── custom_pages/                       # UI code distributions
│   └── <distribution_name>/
│       └── <extracted zip contents>
│
├── translations/                       # (optional, --translations flag)
│   └── <lang>/
│       └── <message_type>.csv
│
├── .vdx/
│   └── component_dependencies.json    # Full outbound dependency graph
│
├── .vdx_state.json                    # MD5 checksum state tracker
└── .vdxignore                         # Glob patterns for components to skip
```

---

## MDL File Format (Advanced Syntax)

### IMPORT statements

Outbound dependencies are written as `IMPORT` declarations at the top of the root `.mdl` file. These are derived from Vault's component relationship data and tell you what this component requires to exist.

```mdl
IMPORT Doclifecycle.approval_process__c;
IMPORT Object.product__v;
IMPORT Object.product__v#Field.created_date__v;

RECREATE Object my_object__c (
   ...
)
```

- `IMPORT Type.name;` — depends on a top-level component
- `IMPORT Type.name#SubType.sub_name;` — depends on a specific subcomponent within another component

IMPORT statements are regenerated on every `vdx pull` and are not sent to Vault on push.

### INCLUDES — extracted attribute values

Large or structured attribute values are extracted to sidecar files. The attribute value in the `.mdl` file is replaced with an `<INCLUDES path>` reference:

```mdl
RECREATE Object my_object__c (
   label('My Object'),
   help_content(<INCLUDES help_content.inc>),
   security_options(<INCLUDES security_options.xml>),
   conditions(<INCLUDES conditions.json>)
)
```

The path is relative to the directory containing the `.mdl` file. On `vdx push`, the file contents are inlined back into the MDL before sending to Vault.

Supported extraction types:

| Extension | Triggered by |
|---|---|
| `.xml` | Attribute metadata type `XMLString` |
| `.json` | Attribute metadata type `JSONString`, or attributes `conditions`, `trigger_date` |
| `.inc` | Attributes `email_body`, `notification`, `subject`, `help_content` |
| `.as` | Value contains `<ActionScript>…</ActionScript>` |
| `.js` | Attribute `validator_code` |

### INCLUDES — extracted subcomponents

Subcomponents are extracted into their own subdirectory. A placeholder is left in the parent `.mdl`:

```mdl
RECREATE Object my_object__c (
   label('My Object'),
   <INCLUDES Field/name__v/name__v.mdl>,
   <INCLUDES Field/label__v/label__v.mdl>
)
```

The path is `<SubType>/<sub_name>/<sub_name>.mdl` relative to the parent component directory. On push, the placeholder is replaced with the actual subcomponent content assembled from the subdirectory.

For Java SDK references within MDL attributes:

```mdl
class(<INCLUDES ../../../javasdk/com/veeva/vault/custom/triggers/MyTrigger.java>)
```

Special characters or spaces in paths can be escaped with a backslash.

---

## State Tracking

`.vdx_state.json` stores MD5 checksums for every managed file. On pull, files are only written if the remote content differs from the stored checksum. On push, only files with changed checksums are deployed. Files deleted locally trigger a `DROP` in Vault on the next push.

The state is automatically invalidated when the vdx version changes, forcing a clean pull.

---

## Vault API Notes

- **Always inspect `responseStatus`** — the Vault API returns HTTP 200 even on failure. Check the JSON body for `"SUCCESS"`, `"FAILURE"`, or `"WARNING"`.
- **Pagination** — large result sets use `responseDetails.next_page`; vdx traverses these automatically.
- **Async jobs** — packaging and translation export return a `jobId` and must be polled at `/api/{version}/services/jobs/{jobId}`.
- **Client ID** — vdx sends `X-VaultAPI-ClientID: veeva-vault-vdx-client`. Enable this in _Vault Admin → Settings → General Settings_ if Client ID Filtering is active.
