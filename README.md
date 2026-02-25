# **vdx \- Vault Developer eXperience CLI**

**vdx** is a Python command-line tool designed to bridge the gap between Veeva Vault configuration and modern source control. By leveraging the Vault API and Metadata Definition Language (MDL), vdx allows you to track, deploy, and package Vault components locally as code.

## **✨ Features**

* **Metadata Filtering**: Intelligently pulls only components of the metadata class, ensuring your repository stays focused on configuration rather than data records.  
* **Specialized Querying**: Uses the specialized /query/components endpoint to retrieve exact MDL definitions directly from the Vault component registry.  
* **Source Control Syncing**: Organizes discrete .mdl files by component type (e.g., components/DocumentType/vdx\_test\_\_c.mdl).  
* **Smart Deployments**: Push only modified or new components. vdx uses MD5 checksums and a local state tracker to minimize API calls.  
* **Bidirectional Deletions**: If a component is removed from Vault, vdx pull removes the local file. If you delete a local file, vdx push executes a DROP command in Vault.  
* **VPK Packaging**: Bundle local changes into a standard Custom Configuration Migration Package (VPK) and automatically trigger a non-destructive validation job.  
* **Auto-Session Renewal**: Automatically generates a new session ID if it encounters an INVALID\_SESSION\_ID error during long-running operations.

## **🛠 Prerequisites**

* **Python 3.6+**  
* Veeva Vault account with API access and Administrative permissions.

## **🚀 Installation & Setup**

### **1\. Clone and Environment Setup**

Clone the repository and set up a virtual environment to manage dependencies:

\# Clone the repository  
git clone \<your-repo-url\>  
cd vdx

\# Create a virtual environment  
python3 \-m venv venv

\# Activate the environment  
\# On Mac/Linux:  
source venv/bin/activate  
\# On Windows:  
.\\venv\\Scripts\\activate

\# Install dependencies  
python3 \-m pip install requests

### **2\. Global Access (Run anywhere)**

To run vdx from any directory on your machine, create a symbolic link that points to the virtual environment's interpreter.

**Mac/Linux:**

\# Ensure main.py is executable  
chmod \+x vdx\_project/main.py

\# Link the script to your local bin (using the venv python)  
sudo ln \-s "$(pwd)/vdx\_project/main.py" /usr/local/bin/vdx

**Windows (PowerShell Profile):**

Add this to your $PROFILE to use the environment's python automatically:

function vdx { & "C:\\path\\to\\vdx\\venv\\Scripts\\python.exe" "C:\\path\\to\\vdx\\vdx\_project\\main.py" $args }

## **⚙️ Configuration**

### **Environment Variables (.env)**

Store your credentials securely in a .env file in the vdx\_project root:

VAULT\_DNS="your-vault.veevavault.com"  
VAULT\_USERNAME="your.email@company.com"  
VAULT\_PASSWORD="your\_password"

### **.vdxignore**

Prevent system-managed or restricted components from cluttering your repository using standard wildcard matching:

components/Group/system\_group\*  
components/Picklist/\*\_\_sys

## **📖 Usage Guide**

### **vdx login**

Authenticates and retrieves an active API session.

vdx login

### **vdx pull**

Queries Vault for all components of class metadata and downloads their MDL definitions.

vdx pull

* Automatically handles API pagination.  
* Logs WARNING responses (like duplicate query detection) while proceeding with the sync.  
* Truncates large error messages for better console readability.

### **vdx push**

Deploys local changes to Vault.

vdx push  
\# Or use dry-run to preview changes  
vdx push \--dry-run

### **vdx package**

Generates a VPK, uploads it to Vault, and triggers validation.

vdx package

## **🔒 Security**

vdx includes the custom header X-VaultAPI-ClientID: veeva-vault-vdx-client. Ensure your Vault Administrator has allowed this Client ID in *Admin \> Settings \> General Settings* if Client ID Filtering is enabled.