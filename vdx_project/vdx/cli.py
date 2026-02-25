import argparse
import logging
from vdx.auth import login
from vdx.commands.pull import run_pull
from vdx.commands.push import run_push
from vdx.commands.package import run_package

def main():
    parser = argparse.ArgumentParser(description="vdx - Veeva Vault Configuration Manager")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose/debug logging")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    login_parser = subparsers.add_parser("login", help="Authenticate to Vault")
    login_parser.add_argument("-u", "--username", help="Vault Username")
    login_parser.add_argument("-p", "--password", help="Vault Password")
    login_parser.add_argument("-v", "--vault-dns", help="Vault DNS")
    
    subparsers.add_parser("pull", help="Pull component MDLs from Vault")
    
    push_parser = subparsers.add_parser("push", help="Push local MDL changes to Vault")
    push_parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying")
    
    subparsers.add_parser("package", help="Create, import, and validate a VPK")
    
    args = parser.parse_args()
    
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(message)s')
    
    if args.command == "login":
        login(args.vault_dns, args.username, args.password)
    elif args.command == "pull":
        run_pull(args)
    elif args.command == "push":
        run_push(args)
    elif args.command == "package":
        run_package(args)
