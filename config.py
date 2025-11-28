"""
Central configuration file for the outbound automation project.
"""

# --- Google API Scopes ---
# Define the permission scopes needed for all scripts.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/documents'
]

# --- Google Sheet IDs ---
SPREADSHEET_ID = "1knG6IgrVf-Uw884jK2XuffZtiZEmVV30MkP59pHxU6M"

# The sheet containing master meeting data.
MASTER_SHEET_ID = "16iIaSqupVvx0T5qkEJb2glZ6jYt37spAYcNawRe7nE8"

# --- Sheet Names / Ranges ---
REPLY_TRACKER_SHEET_NAME = "Sheet7"   # For reply_tracker.py

# --- Authentication File Paths ---
TOKEN_PATH = "token.json"
CLIENT_SECRET_PATH = "client_secret.json"

# --- Reply Tracker Settings ---
SIGNATURE_MARKERS = [
    "bhargav kulkarni",
    "brand partnerships & alliances",
    "+91 8618818322",
    "nobrokerhood"
]
SIGNATURE_TAG = "| SentBy:Bhargav"