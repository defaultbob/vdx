# vdx \- Vault Developer eXperience CLI

**vdx** is a Python command-line tool designed to bridge the gap between Veeva Vault configuration and modern source control. By leveraging the Vault API 3 and Metadata Definition Language (MDL) 2, vdx allows you to track, deploy, and package Vault components locally as code.

## **✨ Features**

* **Source Control Syncing**: Pull all configuration from vault\_component\_\_v 4 as discrete .mdl files organized by component type.  
* **Smart Deployments**: Push only modified or new components to Vault. vdx uses MD5 checksums and a local state tracker to minimize API calls and avoid exceeding Vault's Burst API limits 5, 6\.  
* **Bidirectional Deletions**: If a component is deleted in Vault, vdx pull removes the local file. If you delete a tracked .mdl file locally, vdx push executes a DROP command in Vault 7\.  
* **VPK Packaging**: Dynamically bundle your local changes into a standard Custom Configuration Migration Package (VPK) 1, 8 and automatically import/validate it.  
* **Auto-Session Renewal**: Vault sessions time out after periods of inactivity 9, 10\. vdx securely stores your credentials to automatically generate a new session ID if it encounters an INVALID\_SESSION\_ID error.  
* **Ignore Configuration**: Use a .vdxignore file to prevent system-managed components from cluttering your repository.

## **🛠 Prerequisites**

* **Python 3.6+**  
* The requests library (pip install requests)  
* A Veeva Vault account with API access and sufficient Administrative permissions 11\.

## **🚀 Installation & Setup**

1. **Generate the Project:** Run the build\_vdx.py script to generate the modularized vdx\_project directory.  
2. **Install Dependencies:**  
3. cd vdx\_project  
4. pip install requests  
5. **Make Executable (Optional \- Mac/Linux):**  
6. chmod \+x main.py  
7. alias vdx="./main.py"

## **⚙️ Configuration**

vdx utilizes several configuration files to maintain environment state and security.

### 1\. Environment Variables (.env)

To avoid entering your credentials every time, configure the following environment variables in your terminal or CI/CD pipeline:

export VAULT\_DNS="promo-vee.veevavault.com"

export VAULT\_USERNAME="your.name@company.com"

export VAULT\_PASSWORD="your\_secure\_password"

### 2\. .vdxignore

Some components (like standard users or system groups) cannot be modified via MDL. Create a .vdxignore file in the root of your project using standard wildcard matching to prevent them from being pulled or pushed.

components/Group/system\_group\*

components/Picklist/system\_\*

### 3\. Local State (.vdx\_state.json)

*(Auto-generated)* This file acts as the "index" for vdx. It tracks the MD5 checksums 12 of your components to determine what needs to be pushed, pulled, or dropped. **You should commit this file to your source control.**

## **📖 Usage Guide**

The vdx tool has four primary commands: login, pull, push, and package.

### vdx login

Authenticates to your Vault and retrieves an active API session ID 9\.

vdx login \-u your.name@company.com \-v promo-vee.veevavault.com

*Note: If you have configured your environment variables, you can simply run vdx login without flags.*

### vdx pull

Queries your Vault for all components and downloads their MDL definitions into the local /components directory 4\.

vdx pull

* Handles API pagination automatically using next\_page to ensure all components are retrieved 13\.  
* Updates .vdx\_state.json with the latest checksums.  
* Deletes local files if they no longer exist in Vault.

### vdx push

Compares your local /components directory against the .vdx\_state.json file.

vdx push

* Identifies modified files and pushes their MDL to Vault's /mdl/execute endpoint.  
* Identifies deleted local files and executes a DROP {type} {name}; command in Vault 7\.

**Dry-Run Mode**To safely see what changes will be deployed without actually modifying Vault, use the \--dry-run flag:

vdx push \--dry-run

### vdx package

Generates a valid custom Configuration Migration Package (VPK) ZIP file from your local components, uploads it to Vault, and triggers a validation job 1, 8\.

vdx package

* Dynamically creates the required vaultpackage.xml manifest 14, 15\.  
* Structures deployment steps into ordered 000000 directories 16\.  
* Automatically generates .md5 checksum files required for custom VPK validation 12\.  
* Uploads to the /api/{version}/vpackages endpoint and runs a non-destructive Validate action. Note: The package is **not** deployed automatically; you can review the validation results in the Vault UI 17\.

## **🔒 Security & Client IDs**

By default, vdx includes the custom header X-VaultAPI-ClientID: veeva-vault-vdx-client in all API requests 18, 19\. Vault Administrators can enforce Client ID Filtering to monitor integrations and restrict access strictly to trusted Client IDs 20, 21\. Ensure your Vault Admin has allowed this Client ID in *Admin \> Settings \> General Settings* if filtering is enabled.
