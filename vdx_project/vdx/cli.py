import argparse
import logging
from vdx.auth import login
from vdx.commands.pull import run_pull
from vdx.commands.push import run_push
from vdx.commands.package import run_package
from vdx.commands.clean import run_clean
from vdx.utils import load_dotenv

def main():
    # Load .env variables into os.environ before anything else runs
    load_dotenv()

    parser = argparse.ArgumentParser(description="vdx - Veeva Vault Configuration Manager")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose/debug logging")
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    login_parser = subparsers.add_parser("login", help="Authenticate to Vault")
    login_parser.add_argument("-u", "--username", help="Vault Username")
    login_parser.add_argument("-p", "--password", help="Vault Password")
    login_parser.add_argument("-v", "--vault-dns", help="Vault DNS")
    login_parser.add_argument("--verbose", action="store_true", help=argparse.SUPPRESS)
    
    pull_parser = subparsers.add_parser("pull", help="Pull all component types from Vault (MDL, SDK, Pages, etc.)")
    pull_parser.add_argument("--verbose", action="store_true", help=argparse.SUPPRESS)
    pull_parser.add_argument("--translations", action="store_true", help="Include bulk translations in the pull operation.")
    
    push_parser = subparsers.add_parser("push", help="Push local changes to Vault (MDL, SDK, Pages, etc.)")
    push_parser.add_argument("--dry-run", action="store_true", help="Print changes without modifying")
    push_parser.add_argument("--verbose", action="store_true", help=argparse.SUPPRESS)
    push_parser.add_argument("--translations", action="store_true", help="Include bulk translations in the push operation.")
    
    package_parser = subparsers.add_parser("package", help="Create, import, and validate a VPK")
    package_parser.add_argument("--verbose", action="store_true", help=argparse.SUPPRESS)
    
    clean_parser = subparsers.add_parser("clean", help="Remove local cache files (.vdx_config, .vdx_state.json)")
    clean_parser.add_argument("--verbose", action="store_true", help=argparse.SUPPRESS)
    
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
    elif args.command == "clean":
        run_clean(args)
