# vdx - Vault Developer eXperience CLI

**vdx** is a Python command-line tool designed to bridge the gap between Veeva Vault configuration and modern source control. By leveraging the Vault API and Metadata Definition Language (MDL), vdx allows you to track, deploy, and package Vault components locally as code.

## **✨ Features**

* **Metadata Filtering**: Intelligently pulls only components of the `metadata` class, ensuring your repository stays focused on configuration rather than data records.
* **Specialized Querying**: Uses the specialized `/query/components` endpoint to retrieve exact MDL definitions directly from the Vault component registry.
* **Source Control Syncing**: Organizes discrete `.mdl` files by component type (e.g., `components/DocumentType/vdx_test__c.mdl`).
* **Smart Deployments**: Push only modified or new components. vdx uses MD5 checksums and a local state tracker to minimize API calls.
* **Bidirectional Deletions**: If a component is removed from Vault, `vdx pull` removes the local file. If you delete a local file, `vdx push` executes a `DROP` command in Vault.
* **VPK Packaging**: Bundle local changes into a standard Custom Configuration Migration Package (VPK) and automatically trigger a non-destructive validation job.
* **Auto-Session Renewal**: Automatically generates a new session ID if it encounters an `INVALID_SESSION_ID` error during long-running operations.

## **🛠 Prerequisites**

* **Python 3.6+**
* Veeva Vault account with API access and Administrative permissions.

## **🚀 Installation & Setup**

### 1. Clone and Environment Setup

Clone the repository and set up a virtual environment to manage dependencies:

```bash
# Clone the repository
git clone <your-repo-url>
cd vdx

# Create a virtual environment
python3 -m venv venv

# Activate the environment
# On Mac/Linux:
source venv/bin/activate
# On Windows:
.\venv\Scripts\activate

# Install dependencies
python3 -m pip install requests
```

### 2. Global Access (Run anywhere)

To run `vdx` from any directory on your machine, create a symbolic link that points to the virtual environment's interpreter.

**Mac/Linux:**

```bash
# Ensure main.py is executable
chmod +x vdx_project/main.py

# Link the script to your local bin (using the venv python)
sudo ln -s "$(pwd)/vdx_project/main.py" /usr/local/bin/vdx
```

**Windows (PowerShell Profile):**
Add this to your `$PROFILE` to use the environment's python automatically:

```powershell
function vdx { & "C:\path\to\vdx\venv\Scripts\python.exe" "C:\path\to\vdx\vdx_project\main.py" $args }
```

## **⚙️ Configuration**

### Environment Variables (`.env`)

Store your credentials securely in a `.env` file in the `vdx_project` root:

```bash
VAULT_DNS="your-vault.veevavault.com"
VAULT_USERNAME="your.email@company.com"
VAULT_PASSWORD="your_password"
```

### `.vdxignore`

Prevent system-managed or restricted components from cluttering your repository using standard wildcard matching:

```text
components/Group/system_group*
components/Picklist/*__sys
```

## **📖 Usage Guide**

### `vdx login`

Authenticates and retrieves an active API session.

```bash
vdx login
```

### `vdx pull`

Queries Vault for all components of class `metadata` and downloads their MDL definitions.

```bash
vdx pull
```

* Automatically handles API pagination.
* Logs `WARNING` responses (like duplicate query detection) while proceeding with the sync.
* Truncates large error messages for better console readability.

### `vdx push`

Deploys local changes to Vault.

```bash
vdx push
# Or use dry-run to preview changes
vdx push --dry-run
```

### `vdx package`

Generates a VPK, uploads it to Vault, and triggers validation.

```bash
vdx package
```

## **🔒 Security**

vdx includes the custom header `X-VaultAPI-ClientID: veeva-vault-vdx-client`. Ensure your Vault Administrator has allowed this Client ID in *Admin > Settings > General Settings* if Client ID Filtering is enabled.


## **🧠 Vault Data Model & File Structure Reference**

This section is designed to provide context for AI coding agents or developers analyzing the output of `vdx`. It outlines how Veeva Vault components are represented locally, their structure, and how they map to Vault APIs.

### 1. File Structure Overview

When a Vault is pulled using `vdx pull`, the workspace is populated with specific directory structures based on the component types and classifications:

*   **`components/`**: Stores Vault `metadata` components.
    *   Organized by component type (e.g., `components/Object/`, `components/Docfield/`, `components/Reporttype/`).
    *   **`.mdl` files**: The core configuration scripts (e.g., `my_object__c.mdl`).
    *   **`.d` files**: Bidirectional dependency graphs for the component (e.g., `my_object__c.d`).
    *   **`METADATA-{type}.json`**: Type-level metadata definition (e.g., `METADATA-Object.json`).
*   **`javasdk/`**: Stores Vault `code` components (Java SDK).
    *   Files are downloaded as raw `.java` files.
    *   Organized into standard Java package directory structures parsed directly from the source code (e.g., `javasdk/com/veeva/vault/custom/triggers/MyTrigger.java`).
*   **`custom_pages/`**: Stores UI code distributions.
    *   Organized by distribution name (e.g., `custom_pages/hello_world__c/index.html`).
    *   Files are downloaded by extracting Vault zip distributions from the `/uicode/distributions/{name}/code` endpoint.
*   **`translations/`**: Stores bulk message translations.
    *   Organized by language code and message type (e.g., `translations/en/field_labels__sys.csv`).
    *   Extracted using Vault's asynchronous translation export jobs.

### 2. Metadata Definition Language (MDL)

Vault configuration is defined using MDL (Metadata Definition Language), Veeva's proprietary domain-specific language.

*   **Syntax**: Resembles a combination of SQL DDL and JSON/Object notation.
*   **Retrieval**: `vdx` uses the specialized VQL query endpoint (`/api/{version}/query/components`) to extract the exact MDL string natively generated by Vault.
    *   Example Query: `SELECT component_name__v, component_type__v, mdl_definition__v FROM vault_component__v WHERE component_type__v CONTAINS ('Object', 'Docfield')`
*   **Execution**: When deploying changes, `vdx push` executes the `.mdl` scripts against Vault's `/api/{version}/mdl/execute` endpoint. It parses commands like `RECREATE`, `ALTER`, or `DROP`.

### 3. Component Dependencies (`.d` files)

Vault tracks deep relationships between components internally. `vdx` extracts these relationships and surfaces them as `.d` (dependency) text files alongside the `.mdl` files.

*   **Source**: Queried from the `vault_component_relationship__sys` object.
*   **Format**: Plain text, bidirectional dependency graph.
    ```text
    depends_on: Object.user_role_setup__v [blocking=true]
    used_by: Matchingrule.editor_project__c [blocking=false] [target_sub=Field.related_project__c]
    ```
*   **Meaning**:
    *   `depends_on`: Outbound requirement. The current component requires this target component to exist.
    *   `used_by`: Inbound usage. Another component requires this component.
    *   `[blocking=true]`: A critical directive indicating that the dependent component **cannot** be created or deployed unless the target dependency is satisfied. It also dictates cascading delete behaviors.
    *   `[target_sub=...]`: Indicates the dependency is tied to a specific sub-component (like a specific Field within an Object), not just the top-level component.

### 4. Incremental State Tracking

To optimize API usage and deployment speed, `vdx` tracks the state of the workspace.

*   **`.vdx_state.json`**: A local manifest storing MD5 checksums of every file pulled from or pushed to Vault.
*   **Logic**: During a `push`, `vdx` hashes local files and compares them against the state file. Only modified or new files are deployed. If a file exists in the state but is deleted locally, `vdx` attempts to execute a `DROP` command for that component in Vault.

### 5. API Paradigms & Constraints

*   **Always HTTP 200**: The Vault API often returns HTTP `200 OK` even when an operation fails. `vdx` (and any interacting agent) must inspect the `responseStatus` field within the JSON body (expecting `"SUCCESS"`, `"FAILURE"`, or `"WARNING"`).
*   **Pagination**: Queries returning many records use `responseDetails.next_page` URLs, which `vdx` automatically traverses.
*   **Asynchronous Jobs**: Heavy operations (like packaging and translation extraction) return a `jobId`. `vdx` polls the `/services/jobs/{job_id}` endpoint until the `status` indicates `SUCCESS` before proceeding.
