import requests
from vdx.auth import get_config, login, API_VERSION, CLIENT_ID

def make_vault_request(method, endpoint, **kwargs):
    config = get_config()
    url = f"https://{config['vault_dns']}{endpoint}"
    
    headers = kwargs.pop('headers', {})
    headers["Authorization"] = config.get("session_id", "")
    headers["X-VaultAPI-ClientID"] = CLIENT_ID
    
    response = requests.request(method, url, headers=headers, **kwargs)
    
    if response.status_code == 401 or (response.status_code == 400 and "INVALID_SESSION_ID" in response.text):
        print("Session expired. Automatically generating new session ID...")
        config = login(silent=True)
        headers["Authorization"] = config["session_id"]
        response = requests.request(method, url, headers=headers, **kwargs)
        
    return response
