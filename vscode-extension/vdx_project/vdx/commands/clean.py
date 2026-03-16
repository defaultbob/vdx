import os
import logging
import shutil
from vdx.auth import CONFIG_FILE
from vdx.utils import STATE_FILE

def run_clean_cache(args):
    """Removes local cache files."""
    logging.info("Cleaning local cache files...")
    files_to_remove = [CONFIG_FILE, STATE_FILE]
    for f in files_to_remove:
        if os.path.exists(f):
            try:
                os.remove(f)
                logging.info(f"Removed {f}")
            except OSError as e:
                logging.error(f"Error removing file {f}: {e}")
    logging.info("Cache clean complete.")

def run_clean_files(args):
    """Removes all pulled component and source files."""
    logging.info("Cleaning pulled files...")
    
    dirs_to_remove = ["components", "javasdk", "custom_pages"]
    if getattr(args, 'include_translations', False):
        dirs_to_remove.append("translations")
        logging.info("Including translations in cleanup.")
    else:
        logging.info("Excluding translations from cleanup.")

    for d in dirs_to_remove:
        if os.path.exists(d):
            try:
                shutil.rmtree(d)
                logging.info(f"Removed directory: {d}")
            except Exception as e:
                logging.error(f"Error removing directory {d}: {e}")

    # Clean cache as well
    run_clean_cache(args)
    logging.info("Files and cache clean complete.")
