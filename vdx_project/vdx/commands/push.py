import os
import logging
import zipfile
import io
from pathlib import Path
import json
from vdx.utils import load_state, save_state, compute_checksum, is_ignored, load_ignore_patterns
from vdx.api import make_vault_request, API_VERSION

def _handle_push_response(response, context=""):
    """
    Centralized handler for push API responses.
    """
    # The make_vault_request function already logs the full body on any API failure.
    # This function's job is to interpret the success/failure of a push operation.

    # MDL execute has a different success payload
    if "mdl/execute" in response.url:
        try:
            data = response.json()
            if data.get('responseStatus') == 'SUCCESS':
                logging.info(f"{context}MDL script executed successfully.")
                return True
            else:
                logging.error(f"{context}MDL script execution failed.")
                return False
        except json.JSONDecodeError:
            logging.error(f"{context}Failed to parse MDL response as JSON.")
            logging.debug(f"[API DEBUG] Raw Response Body:\n{response.text}")
            logging.debug("[API DEBUG] Expected a JSON object with a 'responseStatus' key.")
            return False

    # All other modern APIs use this pattern
    try:
        # Some successful responses (like DELETE) might have no body.
        if response.status_code == 200 and not response.content:
            logging.info(f"{context}Push successful (no response body).")
            return True
        data = response.json()
        if data.get("responseStatus") == "SUCCESS":
            logging.info(f"{context}Push successful.")
            return True
        else:
            logging.error(f"{context}Push operation reported a failure.")
            return False
    except json.JSONDecodeError:
        logging.error(f"{context}Failed to parse push response as JSON.")
        logging.debug(f"[API DEBUG] Raw Response Body:\n{response.text}")
        logging.debug("[API DEBUG] Expected a JSON object with a 'responseStatus' key.")
        return False

def push_mdl_changes(changes, deletions, dry_run=False):
    if not changes and not deletions:
        return 0

    logging.info(f"Processing {len(changes)} MDL update(s) and {len(deletions)} deletion(s)...")
    mdl_script = ""
    for path in changes:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        mdl_script += f"CREATE OR UPDATE COMPONENT \n{content}\n;\n"

    for path in deletions:
        parts = Path(path).parts
        comp_type = parts[-2]
        comp_name = Path(parts[-1]).stem
        mdl_script += f"DROP COMPONENT {comp_type}.\"{comp_name}\";\n"

    if dry_run:
        logging.info("[DRY RUN] MDL script to be executed:")
        print(mdl_script)
        return len(changes) + len(deletions)

    endpoint = f"/api/{API_VERSION}/mdl/execute"
    response = make_vault_request("POST", endpoint, data=mdl_script, headers={'Content-Type': 'text/plain'})
    _handle_push_response(response, "MDL Push: ")
    return len(changes) + len(deletions)

def push_java_sdk_changes(changes, deletions, dry_run=False):
    if deletions:
        logging.warning(f"Deletion of Java SDK components is not supported via this API. Skipping {len(deletions)} deletion(s).")
    if not changes:
        return 0

    logging.info(f"Processing {len(changes)} Java SDK file update(s)...")
    updated_count = 0
    for path in changes:
        rel_path = os.path.relpath(path, 'javasdk')
        class_name = Path(rel_path).with_suffix('').as_posix().replace('/', '.')
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        logging.info(f"Pushing Java class: {class_name}")
        if dry_run:
            logging.info(f"[DRY RUN] Would push {path} to component {class_name}")
            updated_count += 1
            continue

        endpoint = f"/api/{API_VERSION}/code/{class_name}"
        response = make_vault_request("PUT", endpoint, data=content.encode('utf-8'), headers={'Content-Type': 'text/plain;charset=UTF-8'})
        if _handle_push_response(response, f"Push {class_name}: "):
            updated_count += 1
    return updated_count

def push_custom_page_changes(changed_dirs, deleted_dirs, dry_run=False):
    updated_count = 0
    if changed_dirs:
        logging.info(f"Processing {len(changed_dirs)} Custom Page distribution update(s)...")
        for dist_dir in changed_dirs:
            dist_name = os.path.basename(dist_dir)
            logging.info(f"Re-packaging and pushing distribution: {dist_name}")

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(dist_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, dist_dir)
                        zf.write(file_path, arcname)
            zip_buffer.seek(0)

            if dry_run:
                logging.info(f"[DRY RUN] Would push zipped content of {dist_dir}")
                updated_count += 1
                continue

            endpoint = f"/api/{API_VERSION}/uicode/distributions"
            files = {'file': (f'{dist_name}.zip', zip_buffer, 'application/zip')}
            response = make_vault_request("POST", endpoint, files=files)
            if _handle_push_response(response, f"Push {dist_name}: "):
                updated_count += 1

    if deleted_dirs:
        logging.info(f"Processing {len(deleted_dirs)} Custom Page distribution deletion(s)...")
        for dist_dir in deleted_dirs:
            dist_name = os.path.basename(dist_dir)
            logging.info(f"Deleting distribution: {dist_name}")
            if dry_run:
                logging.info(f"[DRY RUN] Would delete distribution {dist_name}")
                updated_count += 1
                continue
            
            endpoint = f"/api/{API_VERSION}/uicode/distributions/{dist_name}"
            response = make_vault_request("DELETE", endpoint)
            if _handle_push_response(response, f"Delete {dist_name}: "):
                updated_count += 1
    return updated_count

def push_translation_changes(changes, dry_run=False):
    if not changes:
        return 0
    
    logging.info(f"Processing {len(changes)} translation file update(s)...")
    updated_count = 0
    for path in changes:
        parts = Path(path).parts
        lang = parts[-2]
        msg_type = Path(parts[-1]).stem
        
        logging.info(f"Pushing translations for {msg_type} in language '{lang}'")
        if dry_run:
            logging.info(f"[DRY RUN] Would push {path}")
            updated_count += 1
            continue

        endpoint = f"/api/{API_VERSION}/messages/actions/import"
        data = {'message_type': msg_type, 'language': lang}
        with open(path, 'rb') as f:
            files = {'file': (os.path.basename(path), f.read(), 'text/csv')}
            response = make_vault_request("POST", endpoint, data=data, files=files)
            if _handle_push_response(response, f"Push {path}: "):
                updated_count += 1
    return updated_count

def run_push(args):
    logging.info("Starting push process...")
    if args.dry_run:
        logging.info("--- DRY RUN MODE ---")
        
    state = load_state()
    ignore_patterns = load_ignore_patterns()
    
    local_files = {}
    tracked_dirs = ["components", "javasdk", "custom_pages", "translations"]
    for directory in tracked_dirs:
        if not os.path.exists(directory):
            continue
        for root, _, files in os.walk(directory):
            for file in files:
                path = os.path.join(root, file)
                if not is_ignored(path, ignore_patterns):
                    local_files[path] = compute_checksum(open(path, 'rb').read())

    new_or_changed_files = [path for path, checksum in local_files.items() if state.get(path) != checksum]
    deleted_files = [path for path in state.keys() if path not in local_files]

    mdl_changes = [p for p in new_or_changed_files if p.startswith("components" + os.sep)]
    mdl_deletions = [p for p in deleted_files if p.startswith("components" + os.sep)]
    
    java_changes = [p for p in new_or_changed_files if p.startswith("javasdk" + os.sep)]
    java_deletions = [p for p in deleted_files if p.startswith("javasdk" + os.sep)]
    
    translation_changes = [p for p in new_or_changed_files if p.startswith("translations" + os.sep)]

    changed_page_dirs = set()
    for path in new_or_changed_files:
        if path.startswith("custom_pages" + os.sep):
            dist_dir = os.path.join(*Path(path).parts[:2])
            changed_page_dirs.add(dist_dir)
            
    deleted_page_dirs = set()
    for path in deleted_files:
        if path.startswith("custom_pages" + os.sep):
            dist_dir = os.path.join(*Path(path).parts[:2])
            if not os.path.exists(dist_dir):
                deleted_page_dirs.add(dist_dir)
            else:
                changed_page_dirs.add(dist_dir)

    total_updated = 0
    total_updated += push_mdl_changes(mdl_changes, mdl_deletions, args.dry_run)
    total_updated += push_java_sdk_changes(java_changes, java_deletions, args.dry_run)
    total_updated += push_custom_page_changes(list(changed_page_dirs), list(deleted_page_dirs), args.dry_run)
    total_updated += push_translation_changes(translation_changes, args.dry_run)

    if not args.dry_run:
        logging.info("Updating local state...")
        save_state(local_files)
        logging.info("Push complete.")
    else:
        logging.info("--- DRY RUN COMPLETE ---")
        logging.info(f"Found {total_updated} total change(s) to push.")