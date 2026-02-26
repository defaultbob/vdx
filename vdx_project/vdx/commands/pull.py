import os
import sys
import logging
import json
import time
import io
import zipfile
import re
from vdx.api import make_vault_request, API_VERSION
from vdx.utils import compute_checksum, load_state, save_state, load_ignore_patterns, is_ignored
def truncate_error(data):
    """
    Truncates the error message to the first 1000 characters or 50 lines 
    to prevent console flooding from large API responses.
    """
    text = json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data)
    
    # Truncate by characters
    if len(text) > 1000:
        text = text[:1000] + "... [TRUNCATED]"
    
    # Truncate by lines
    lines = text.splitlines()
    if len(lines) > 50:
        text = "\n".join(lines[:50]) + "\n... [TRUNCATED LINES]"
        
    return text

def _handle_api_response(response, context=""):
    """
    Centralized handler for API response status, warnings, and errors.
    Returns the JSON data if successful, otherwise None.
    """
    # The make_vault_request function handles non-200s and logs them.
    if response.status_code != 200:
        logging.error(f"{context}Request failed.")
        return None
        
    try:
        data = response.json()
    except json.JSONDecodeError:
        logging.error(f"{context}Failed to parse API response as JSON.")
        logging.debug(f"[API DEBUG] Raw Response Body:\n{response.text}")
        logging.debug("[API DEBUG] Expected a JSON object with a 'responseStatus' key (e.g., {\"responseStatus\": \"SUCCESS\", ...}).")
        return None

    status = data.get("responseStatus")
    
    if status == "WARNING":
        warning_info = data.get("warnings") or "Unknown warning occurred."
        logging.warning(f"{context}Vault API Warning: {truncate_error(warning_info)}")
    elif status != "SUCCESS":
        # The make_vault_request function already logs the full body on FAILURE.
        logging.error(f"{context}API call reported non-SUCCESS status.")
        return None
    
    return data

def _update_local_file(file_path, content, state, is_binary=False):
    """Helper to write file, update state, and return status if updated."""
    remote_checksum = compute_checksum(content)
    local_checksum = state.get(file_path, "")

    if local_checksum != remote_checksum:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        mode = 'wb' if is_binary else 'w'
        encoding = None if is_binary else 'utf-8'
        with open(file_path, mode, encoding=encoding) as f:
            f.write(content)
        state[file_path] = remote_checksum
        logging.info(f"Updated: {file_path}")
        return True
    return False

def pull_mdl_components(state, ignore_patterns):
    """Pulls MDL for 'metadata' class components."""
    logging.info("Pulling MDL components...")
    vault_files = {}
    updated_count = 0

    # 1. Get component types for 'metadata' class
    logging.debug("Fetching component metadata to identify 'metadata' class types...")
    meta_endpoint = f"/api/{API_VERSION}/metadata/components"
    meta_response = make_vault_request("GET", meta_endpoint)
    meta_data = _handle_api_response(meta_response, "Component Metadata: ")
    if not meta_data:
        return {}, 0
    
    metadata_types = [
        comp["name"] for comp in meta_data.get("data", []) 
        if comp.get("class") == "metadata"
    ]
    
    if not metadata_types:
        logging.info("No 'metadata' class component types found.")
        return {}, 0
    
    # 2. Build and execute VQL query
    types_list = ", ".join([f"'{t}'" for t in metadata_types])
    query = f"SELECT component_name__v, component_type__v, mdl_definition__v FROM vault_component__v WHERE component_type__v CONTAINS ({types_list})"
    endpoint = f"/api/{API_VERSION}/query/components"
    response = make_vault_request("POST", endpoint, data={"q": query})
    data = _handle_api_response(response, "MDL Components: ")
    if not data:
        return {}, 0

    records = data.get("data", [])
    current_data = data
    while current_data.get("responseDetails", {}).get("next_page"):
        next_url = current_data["responseDetails"]["next_page"]
        logging.info("Traversing next page for MDL...")
        response = make_vault_request("GET", next_url)
        current_data = response.json()
        records.extend(current_data.get("data", []))

    base_dir = "components"
    for record in records:
        comp_type = record.get("component_type__v")
        comp_name = record.get("component_name__v")
        mdl_def = record.get("mdl_definition__v", "")
        if not comp_type or not comp_name:
            logging.warning("Skipping record with missing name or type.")
            continue

        file_path = os.path.join(base_dir, comp_type, f"{comp_name}.mdl")
        if is_ignored(file_path, ignore_patterns):
            continue

        vault_files[file_path] = True
        if _update_local_file(file_path, mdl_def, state):
            updated_count += 1

    return vault_files, updated_count

def pull_java_sdk(state, ignore_patterns):
    """Pulls 'code' class components as individual Java files."""
    logging.info("Pulling Java SDK source files...")
    vault_files = {}
    updated_count = 0
    base_dir = "javasdk"

    # 1. Get component types for 'code' class
    logging.debug("Fetching component metadata to identify 'code' class types...")
    meta_endpoint = f"/api/{API_VERSION}/metadata/components"
    meta_response = make_vault_request("GET", meta_endpoint)
    meta_data = _handle_api_response(meta_response, "Component Metadata: ")
    if not meta_data:
        return {}, 0
        
    code_types = [
        comp["name"] for comp in meta_data.get("data", []) 
        if comp.get("class") == "code"
    ]
    
    if not code_types:
        logging.info("No 'code' class component types found.")
        return {}, 0

    # 2. Build and execute VQL query for component names
    types_list = ", ".join([f"'{t}'" for t in code_types])
    query = f"SELECT component_name__v FROM vault_component__v WHERE component_type__v CONTAINS ({types_list})"
    endpoint = f"/api/{API_VERSION}/query/components"
    response = make_vault_request("POST", endpoint, data={"q": query})
    data = _handle_api_response(response, "Java SDK Components: ")
    if not data:
        return {}, 0

    for record in data.get("data", []):
        comp_name = record.get("component_name__v")
        if not comp_name:
            continue

        # Filter by namespace *before* making the API call to avoid errors on system components
        if not comp_name.startswith("com.veeva.vault.custom"):
            logging.debug(f"Skipping '{comp_name}' as it is not in the 'com.veeva.vault.custom' namespace.")
            continue

        code_endpoint = f"/api/{API_VERSION}/code/{comp_name}"
        resp = make_vault_request("GET", code_endpoint)

        # The API can return 200 OK but with a FAILURE status in the JSON body (e.g., file not found).
        # We check for this case before attempting to process the text as source code.
        try:
            if resp.json().get("responseStatus") == "FAILURE":
                # The API wrapper in make_vault_request already logged the detailed error.
                continue
        except json.JSONDecodeError:
            # Not a JSON response, so it's likely the source code we want.
            pass

        if resp.status_code != 200:
            logging.error(f"Failed to download source for '{comp_name}'. HTTP {resp.status_code}")
            continue

        source_code = resp.text
        package_match = re.search(r"^\s*package\s+([a-zA-Z0-9_.]+);", source_code, re.MULTILINE)

        if not package_match:
            logging.warning(f"Could not parse package for '{comp_name}'. File may be invalid or an unexpected API error response.")
            continue

        package_name = package_match.group(1)
        package_path = package_name.replace('.', os.path.sep)
        file_path = os.path.join(base_dir, package_path, f"{comp_name}.java")

        if is_ignored(file_path, ignore_patterns):
            continue

        vault_files[file_path] = True
        if _update_local_file(file_path, source_code, state):
            updated_count += 1

    return vault_files, updated_count

def pull_custom_pages(state, ignore_patterns):
    """Pulls and extracts Custom Page distributions."""
    logging.info("Pulling and extracting Custom Page distributions...")
    vault_files = {}
    updated_count = 0
    base_dir = "custom_pages"

    endpoint = f"/api/{API_VERSION}/uicode/distributions"
    response = make_vault_request("GET", endpoint)
    data = _handle_api_response(response, "Custom Pages: ")
    if not data:
        logging.warning("Could not retrieve custom page distributions. Response was empty or contained errors.")
        return {}, 0

    distributions = data.get("data", [])
    if not distributions:
        logging.info("No custom page distributions found in Vault.")
        return {}, 0

    logging.info(f"Found {len(distributions)} custom page distribution(s) to process.")
    for dist in distributions:
        dist_name = dist.get("name")
        
        download_endpoint = f"/api/{API_VERSION}/uicode/distributions/{dist_name}/code"
        resp = make_vault_request("GET", download_endpoint)

        # Handle cases where the API returns a JSON error instead of a file
        try:
            if resp.json().get("responseStatus") == "FAILURE":
                # The API wrapper already logged the error details.
                continue
        except json.JSONDecodeError:
            # This is expected for a successful file download (it's not JSON).
            pass

        if resp.status_code != 200:
            logging.error(f"Failed to download page distribution '{dist_name}'. HTTP {resp.status_code}")
            continue

        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zip_file:
                for info in zip_file.infolist():
                    if info.is_dir():
                        continue
                    
                    file_path = os.path.join(base_dir, dist_name, info.filename)
                    if is_ignored(file_path, ignore_patterns):
                        continue
                    
                    vault_files[file_path] = True
                    file_content = zip_file.read(info.filename)
                    
                    if _update_local_file(file_path, file_content, state, is_binary=True):
                        updated_count += 1
        except zipfile.BadZipFile:
            logging.error(f"Failed to process page distribution '{dist_name}'. It may not be a valid zip file.")

    return vault_files, updated_count

def pull_translations(state, ignore_patterns):
    """Exports and pulls bulk translation files per language and message type, as per spec."""
    logging.info("Pulling bulk translations...")
    vault_files = {}
    updated_count = 0
    base_dir = "translations"

    # 1. Get active languages from Vault
    lang_endpoint = f"/api/{API_VERSION}/query"
    lang_query = "SELECT admin_key__sys FROM language__sys"
    lang_response = make_vault_request("POST", lang_endpoint, data={"q": lang_query})
    lang_data = _handle_api_response(lang_response, "Languages Query: ")
    if not lang_data:
        return {}, 0
    languages = [item['admin_key__sys'] for item in lang_data.get('data', [])]
    logging.info(f"Found active languages: {languages}")

    # 2. Define message types as per spec
    message_types = ['field_labels__sys', 'system_messages__sys', 'notification_template_messages__sys', 'user_account_messages__sys']

    # 3. Loop through each language and message type to export, poll, and download
    for lang in languages:
        for msg_type in message_types:
            logging.info(f"Exporting {msg_type} for language '{lang}'...")

            # Start export job
            export_endpoint = f"/api/{API_VERSION}/messages/{msg_type}/language/{lang}/actions/export"
            job_start_response = make_vault_request("POST", export_endpoint)
            job_data = _handle_api_response(job_start_response, f"Export {msg_type}/{lang}: ")
            # The response has a nested data object with 'jobId'
            if not job_data or 'data' not in job_data or 'jobId' not in job_data.get('data', {}):
                # This can happen if there are no translations for the given type/language. The API returns SUCCESS but no job is created.
                logging.info(f"No export job started for {msg_type}/{lang}. This usually means there are no translations to export.")
                continue
            job_id = job_data['data']['jobId']

            # Poll job until completion
            while True:
                # This job type uses the /services/jobs endpoint
                status_endpoint = f"/api/{API_VERSION}/services/jobs/{job_id}"
                status_resp = make_vault_request("GET", status_endpoint)

                try:
                    status_data = status_resp.json()
                    if status_data.get("responseStatus") != "SUCCESS":
                        logging.error(f"Job polling for {job_id} failed: {status_data.get('errors')}")
                        break
                except json.JSONDecodeError:
                    # This can happen if the API call itself failed and returned non-JSON
                    # The make_vault_request function already logs the error in this case.
                    break

                # Per the spec, the job details are in the 'data' object
                job_details = status_data.get("data")
                if not job_details or not isinstance(job_details, dict):
                    logging.error(f"Polling response for job {job_id} is missing or has an invalid 'data' object.")
                    logging.debug(f"[API DEBUG] Raw Response Body:\n{status_resp.text}")
                    logging.debug("[API DEBUG] Expected a JSON object with a 'data' object containing job details.")
                    break

                status = job_details.get("status")

                if status == "SUCCESS":
                    logging.info(f"Job {job_id} completed. Downloading results...")
                    
                    # Find the download link from the job content link
                    download_url = None
                    for link in job_details.get("links", []):
                        if link.get("rel") == "content":
                            download_url = link.get("href")
                            break
                    
                    if not download_url:
                        logging.warning(f"Could not find content download link for completed job {job_id}. Falling back to constructed URL.")
                        # Fallback to the old method if link is not present
                        download_url = f"/api/{API_VERSION}/messages/{msg_type}/language/{lang}/file"

                    results_resp = make_vault_request("GET", download_url)
                    if results_resp.status_code == 200:
                        file_content = results_resp.content
                        file_path = os.path.join(base_dir, lang, f"{msg_type}.csv")
                        if not is_ignored(file_path, ignore_patterns):
                            vault_files[file_path] = True
                            if _update_local_file(file_path, file_content, state, is_binary=True):
                                updated_count += 1
                    else:
                        logging.error(f"Failed to download results for job {job_id} from {download_url}. HTTP {results_resp.status_code}")
                    break  # Exit while loop for this job

                if status in ["ERRORS", "CANCELLED"]:
                    logging.error(f"Job {job_id} for {msg_type}/{lang} failed with status: {status}")
                    break  # Exit while loop
                
                if status is None:
                    logging.error(f"Could not determine status for job {job_id}. Aborting poll for this job.")
                    break

                logging.info(f"Polling job {job_id} ({msg_type}/{lang})... status: {status}")
                time.sleep(10)  # Adhere to 10s limit from spec

    return vault_files, updated_count

def run_pull(args):
    """
    Fetches all supported component types from Vault and synchronizes local directories.
    """
    state = load_state()
    ignore_patterns = load_ignore_patterns()

    all_vault_files = {}
    total_updated = 0
    deleted_count = 0

    pull_functions = [
        pull_mdl_components,
        pull_java_sdk,
        pull_custom_pages,
    ]

    if args.translations:
        logging.info("Including translations in pull operation.")
        pull_functions.append(pull_translations)

    for pull_func in pull_functions:
        try:
            vault_files, updated_count = pull_func(state, ignore_patterns)
            all_vault_files.update(vault_files)
            total_updated += updated_count
        except Exception as e:
            logging.error(f"An unexpected error occurred during {pull_func.__name__}: {e}")
            logging.debug("Traceback:", exc_info=True)

    for tracked_file in list(state.keys()):
        if tracked_file not in all_vault_files:
            if os.path.exists(tracked_file):
                try:
                    os.remove(tracked_file)
                    logging.info(f"Deleted locally (not in Vault): {tracked_file}")
                    deleted_count += 1
                except OSError as e:
                    logging.error(f"Error removing file {tracked_file}: {e}")
            del state[tracked_file]
            
    save_state(state)
    logging.info(f"Pull complete. {total_updated} files updated, {deleted_count} files removed.")
