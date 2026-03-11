import os
import logging

CONFIG_FILE = ".vdx_config"
STATE_FILE = ".vdx_state.json"

def run_clean(args):
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
        else:
            logging.info(f"{f} not found, skipping.")
    logging.info("Clean complete.")