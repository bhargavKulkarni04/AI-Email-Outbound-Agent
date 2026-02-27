
"""
Google Authentication Module
Handles OAuth2 login for Gmail, Sheets, Docs, and Drive APIs.
Returns authenticated service objects for use across all Phase 2 scripts.
"""

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os
import config


def login():
    """Authenticates with Google and returns the credentials object."""
    creds = None

    if os.path.exists(config.TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(config.TOKEN_PATH, config.SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(config.CLIENT_SECRET_PATH, config.SCOPES)
            creds = flow.run_local_server(port=0)
        with open(config.TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())

    return creds


def get_services():
    """Returns all Google API service objects needed for Phase 2."""
    creds = login()
    return {
        "gmail": build("gmail", "v1", credentials=creds),
        "sheets": build("sheets", "v4", credentials=creds),
        "docs": build("docs", "v1", credentials=creds),
        "drive": build("drive", "v3", credentials=creds),
    }
