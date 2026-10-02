"""
Script to verify Salesforce credentials and login from the command line.

Usage:
    python scripts/test_login.py --username user@example.com --password mypass --client-id 3MVG9...
    python scripts/test_login.py --env
"""

import asyncio
import argparse
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.schemas.auth import SalesforceCredentials
from app.services.sf_auth import sf_auth_client


async def main():
    parser = argparse.ArgumentParser(description="Test Salesforce login and token grant.")
    parser.add_argument("--login-url", default=os.getenv("SF_LOGIN_URL", "https://login.salesforce.com"), help="Salesforce login URL")
    parser.add_argument("--client-id", default=os.getenv("SF_CLIENT_ID"), help="Salesforce Connected App Consumer Key")
    parser.add_argument("--client-secret", default=os.getenv("SF_CLIENT_SECRET"), help="Salesforce Consumer Secret")
    parser.add_argument("--username", default=os.getenv("SF_USERNAME"), help="Salesforce username")
    parser.add_argument("--password", default=os.getenv("SF_PASSWORD"), help="Salesforce password")
    parser.add_argument("--security-token", default=os.getenv("SF_SECURITY_TOKEN"), help="Salesforce security token")
    parser.add_argument("--jwt-key-path", default=os.getenv("SF_JWT_KEY_PATH"), help="Path to RSA private key file for JWT Bearer flow")

    args = parser.parse_args()

    private_key_pem = None
    if args.jwt_key_path and os.path.exists(args.jwt_key_path):
        with open(args.jwt_key_path, "r") as f:
            private_key_pem = f.read()

    if not args.client_id or not args.username:
        print("Error: --client-id and --username are required (or set via environment variables).")
        sys.exit(1)

    try:
        creds = SalesforceCredentials(
            login_url=args.login_url,
            client_id=args.client_id,
            client_secret=args.client_secret,
            username=args.username,
            password=args.password,
            security_token=args.security_token,
            private_key=private_key_pem,
        )
    except Exception as exc:
        print(f"Validation error: {exc}")
        sys.exit(1)

    print(f"[*] Validating credentials for user: {creds.username} on {creds.login_url} (Flow: {creds.auth_flow})...")
    result = await sf_auth_client.validate_credentials(creds)

    if result.valid:
        print("\n[+] SUCCESS! Salesforce login verified successfully.")
        print(f"    - Organization ID : {result.organization_id}")
        print(f"    - User ID         : {result.user_id}")
        print(f"    - Instance URL    : {result.instance_url}")
        print(f"    - Auth Flow       : {result.auth_flow}")
    else:
        print("\n[-] FAILED! Could not log into Salesforce.")
        print(f"    - Message      : {result.message}")
        print(f"    - Error Detail : {result.error_detail}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
