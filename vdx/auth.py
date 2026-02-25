import os
import json
import requests
import sys
from getpass import getpass

CONFIG_FILE = ".vdx_config"
API_VERSION = "v25.3"
CLIENT_ID = "veeva-vault-vdx-client"

def print_ascii_art():
    art = '''
 __     __  _____   __   __ 
 \ \   / / |  __ \  \ \ / / 
  \ \_/ /  | |  | |  \ V /  
   \   /   | |  | |   > <   
    \_/    |____/   /_/ \_\ 
    Vault Developer eXperience
    '''
    print(art)

def login(dns=None, username=None, password=None, silent=False):
    if not silent:
        print_ascii_art()

    config = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

    dns = dns or os.getenv("VAULT_DNS") or config.get("vault_dns")
    username = username or os.getenv("VAULT_USERNAME") or config.get("username")
    password = password or os.getenv("VAULT_PASSWORD") or config.get("password")

    if not dns or not username:
        print("Error: VAULT_DNS and VAULT_USERNAME are required.")
        sys.exit(1)
        
    if not password:
        password = getpass(f"Vault Password for {username}: ")

    url = f"https://{dns}/api/{API_VERSION}/auth"
    payload = {"username": username, "password": password}
    
    if not silent: print(f"Authenticating to {dns}...")
    
    response = requests.post(url, data=payload, headers={"X-VaultAPI-ClientID": CLIENT_ID})
    
    if response.status_code == 200:
        session_id = response.json().get("sessionId")
        config = {
            "vault_dns": dns, 
            "username": username,
            "password": password,
            "session_id": session_id
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f)
            
        if not silent: print("Login successful! Session and credentials saved locally.")
        return config
    else:
        print(f"Login failed: {response.text}")
        sys.exit(1)

def get_config():
    if not os.path.exists(CONFIG_FILE):
        print("Error: Not logged in. Run 'vdx login' first.")
        sys.exit(1)
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)
