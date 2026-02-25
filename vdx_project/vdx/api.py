import requests
import logging
from vdx.auth import get_config, login, API_VERSION, CLIENT_ID

def make_vault_request(method, endpoint, **kwargs):
    config = get_config()
    
    # Check if a full URL was passed (like next_page URLs)
    if endpoint.startswith("http"):
        url = endpoint
    else:
        url = f"https://{config['vault_dns']}{endpoint}"
    
    headers = kwargs.pop('headers', {})
    headers["Authorization"] = config.get("session_id", "")
    headers["X-VaultAPI-ClientID"] = CLIENT_ID
    
    logging.debug(f"[API] Request: {method} {url}")
    if 'data' in kwargs and method != 'GET':
        data_str = str(kwargs['data'])
        # Truncate large payloads for readability in debug
        if len(data_str) > 200:
            data_str = data_str[:200] + " ... [TRUNCATED]"
        logging.debug(f"[API] Payload Preview: {data_str}")
        
    response = requests.request(method, url, headers=headers, **kwargs)
    logging.debug(f"[API] Response Status: {response.status_code}")
    
    # Vault sometimes returns HTTP 200 with FAILURE and INVALID_SESSION_ID in the body
    if response.status_code == 401 or "INVALID_SESSION_ID" in response.text:
        logging.info("Session expired. Automatically generating new session ID...")
        config = login(silent=True)
        headers["Authorization"] = config["session_id"]
        response = requests.request(method, url, headers=headers, **kwargs)
        logging.debug(f"[API] Retry Response Status: {response.status_code}")
        
    # Standardize error reporting at the API level (enforce responseStatus checking)
    try:
        resp_json = response.json()
        response_status = resp_json.get("responseStatus")
    except ValueError:
        response_status = None

    if response.status_code >= 400 or response_status == "FAILURE":
        logging.error(f"[API ERROR] HTTP {response.status_code} on {method} {url}")
        logging.error(f"[API ERROR] Response Body: {response.text}")
        
    return response
