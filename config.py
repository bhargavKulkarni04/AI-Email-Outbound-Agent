
"""
Central configuration module for the NoBrokerHood Outbound Automation project.
This file centralizes all paths, spreadsheet IDs, and business logic constants.
"""

import os
from dotenv import load_dotenv

# --- Path Configuration ---
# Ensures all file paths are absolute and relative to this file's directory.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))

# --- Sensitive / Environment Data (from .env) ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID", "13qHFawkKa16oDcrWDOam23Dvf5LFaEo6cYRY9kJ0tXw")
MASTER_SHEET_ID = os.getenv("MASTER_SHEET_ID", "16iIaSqupVvx0T5qkEJb2glZ6jYt37spAYcNawRe7nE8")

# --- Authentication Paths ---
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
CLIENT_SECRET_PATH = os.path.join(BASE_DIR, "client_secret.json")
SIGNATURE_GIF_PATH = os.path.join(BASE_DIR, "unnamed.gif")

# --- Google API Settings ---
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/documents'
]

# --- Phase 2: Strategic Lead Settings ---
MEETING_DATA_SHEET = "Meeting_data"
MIN_MEETING_DURATION = 10  # Minutes
PHASE2_FILTERS = {
    "done_status": "Conducted",
    "closure_exclude": "close"
}

# --- Legacy / Reply Tracker Settings ---
REPLY_TRACKER_SHEET = "Sheet7"
SIGNATURE_MARKERS = [
    "bhargav kulkarni",
    "brand partnerships & alliances",
    "+91 8618818322",
    "nobrokerhood"
]
SIGNATURE_TAG = "| SentBy:Bhargav"

# --- AI Model Settings ---
PRIMARY_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "gemini-3-pro-image-preview"