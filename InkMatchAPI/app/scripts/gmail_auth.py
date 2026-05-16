from __future__ import annotations

import argparse
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow


SCOPES = ['https://www.googleapis.com/auth/gmail.send']


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Authorize InkMatch to send mail through a Gmail account and save tokens.',
    )
    parser.add_argument(
        '--client-secrets',
        default='client_secret.json',
        help='Path to the Google OAuth client secrets JSON file.',
    )
    parser.add_argument(
        '--token',
        default='gmail_token.json',
        help='Path where the OAuth token should be saved.',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client_secrets = Path(args.client_secrets)
    token_path = Path(args.token)

    if not client_secrets.exists():
        raise SystemExit(f'Client secrets file not found: {client_secrets}')

    creds: Credentials | None = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.valid:
        print(f'Token already exists and is valid: {token_path}')
        return

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding='utf-8')
        print(f'Token refreshed and saved to: {token_path}')
        return

    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(), encoding='utf-8')
    print(f'Authorization completed. Token saved to: {token_path}')


if __name__ == '__main__':
    main()
