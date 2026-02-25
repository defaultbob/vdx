import os
import sys
import zipfile
import logging
import time
from pathlib import Path
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state

def poll_job_status(job_id):
    """
    Polls the Vault Job API until the job completes.
    Returns the job status data or None if it fails.
    """
    endpoint = f"/api/{API_VERSION}/services/jobs/{job_id}"
    logging.info(f"Monitoring import job {job_id}...")
    
    attempts = 0
    max_attempts = 60  # 12 minutes max (12s intervals)
    
    while attempts < max_attempts:
        response = make_vault_request("GET", endpoint)
        if response.status_code == 200:
            job_data = response.json().get("data", {})
            status = job_data.get("status")
            
            if status == "SUCCESS":
                logging.info("Import job completed successfully.")
                return job_data
            elif status in ["FAILURE", "CANCELLED"]:
                logging.error(f"Job finished with status: {status}")
                return None
            
            logging.debug(f"Job status: {status}. Waiting 12 seconds...")
        else:
            logging.warning(f"Failed to check job status (HTTP {response.status_code}). Retrying...")
            
        time.sleep(12)
        attempts += 1
        
    logging.error("Timed out waiting for import job to complete.")
    return None

def run_package(args):
    base_dir = "components"
    vpk_filename = "vdx_deployment.vpk"
    
    current_file_path = Path(__file__).resolve()
    project_root = current_file_path.parent.parent.parent
    template_path = project_root / "templates" / "vaultpackage.xml"
    
    if not os.path.exists(base_dir):
        logging.error("No /components directory found in the current directory.")
        sys.exit(1)
        
    if not template_path.exists():
        logging.error(f"Package template not found at: {template_path}")
        sys.exit(1)

    state = load_state()
    logging.info("Analyzing local components for changes...")
    
    modified_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".mdl"):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                current_checksum = compute_checksum(content)
                if state.get(file_path) != current_checksum:
                    modified_files.append((file_path, content, current_checksum))

    if not modified_files:
        logging.info("No modified components found. Package creation skipped.")
        sys.exit(0)

    logging.info(f"Packaging {len(modified_files)} modified components into {vpk_filename}...")
    
    with zipfile.ZipFile(vpk_filename, 'w', zipfile.ZIP_DEFLATED) as vpk:
        with open(template_path, 'r', encoding='utf-8') as tf:
            manifest_template = tf.read()
            
        manifest = manifest_template.format(
            package_name="vdx_deployment",
            author="vdx_tool",
            summary=f"Automated VPK containing {len(modified_files)} changes",
            description="Custom VPK generated from local source control"
        )
        vpk.writestr("vaultpackage.xml", manifest)
        
        step_num = 10
        for file_path, mdl_content, md5_hash in modified_files:
            path_parts = Path(file_path).parts
            comp_type = path_parts[-2]
            comp_name = path_parts[-1].replace(".mdl", "")
            
            step_folder = f"{step_num:06d}"
            vpk.writestr(f"components/{step_folder}/{comp_type}.{comp_name}.mdl", mdl_content)
            vpk.writestr(f"components/{step_folder}/{comp_type}.{comp_name}.md5", f"{md5_hash} {comp_type}.{comp_name}")
            step_num += 10
                    
    logging.info(f"Successfully created custom package {vpk_filename}.")
    logging.info("Importing VPK to Vault...")
    import_endpoint = f"/api/{API_VERSION}/services/package"
    
    with open(vpk_filename, 'rb') as f:
        response = make_vault_request("PUT", import_endpoint, files={'file': (vpk_filename, f, 'application/zip')})
        
    if response.status_code == 200 and response.json().get("responseStatus") == "SUCCESS":
        resp_json = response.json()
        job_id = resp_json.get("job_id")
        
        if not job_id:
            # Fallback for older API versions or immediate returns
            package_id = resp_json.get("data", {}).get("package_id__v")
        else:
            job_info = poll_job_status(job_id)
            if not job_info:
                logging.error("Import failed during job execution.")
                sys.exit(1)
            # The package ID is usually in the job results for import jobs
            package_id = job_info.get("package_id__v")
            
        if not package_id:
            logging.error("Could not retrieve Package ID from Vault response.")
            sys.exit(1)

        logging.info(f"Package successfully imported. Vault Package ID: {package_id}")
        
        val_res = make_vault_request("POST", f"/api/{API_VERSION}/services/vobject/vault_package__v/{package_id}/actions/validate/")
        if val_res.status_code == 200 and val_res.json().get("responseStatus") == "SUCCESS":
            logging.info(f"Validation Job initiated successfully.")
        else:
            logging.error(f"Failed to initiate validation job. Response: {val_res.text}")
    else:
        logging.error(f"Error importing package: {response.text}")
