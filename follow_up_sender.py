
import os
import time
import base64
import json
import re
import logging
import pandas as pd
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.message import EmailMessage
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    'https://www.googleapis.com/auth/spreadsheets',
]
SPREADSHEET_ID = "1wSQh-5DXBAD0W2-9Blg1RtQ4berwnBcKnVAlxZLrlxU" # bhargav sheet id
SHEET_NAME = "Sheet7"
TOKEN_PATH = "token.json"
CLIENT_SECRET_PATH = "client_secret.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini Client
try:
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("✅ Gemini model configured successfully.")
except Exception as e:
    print(f"❌ Error configuring Gemini API: {e}")
    exit()

def get_google_creds():
    """Handles Google API authentication flow."""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return creds

def get_sheet_data(service, spreadsheet_id, range_name):
    """Reads data from Google Sheet."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=range_name).execute()
        values = result.get('values', [])
        return values
    except HttpError as error:
        print(f"❌ An error occurred reading sheet: {error}")
        return []

def update_sheet_cell(service, spreadsheet_id, range_name, value):
    """Updates a specific cell or range in the sheet."""
    body = {'values': [[value]]}
    try:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id, range=range_name,
            valueInputOption='RAW', body=body).execute()
        print(f"Updated sheet: {range_name} -> {value}")
    except HttpError as error:
        print(f"❌ An error occurred updating sheet: {error}")

def get_email_body(service, message_id):
    """Fetches the body of a sent email from Gmail."""
    try:
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        payload = message['payload']
        body = ""

        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body += base64.urlsafe_b64decode(data).decode()
        elif payload.get('mimeType') == 'text/plain':
             data = payload['body'].get('data')
             if data:
                body += base64.urlsafe_b64decode(data).decode()
        
        return body
    except Exception as e:
        print(f"⚠️ Could not fetch original email body for {message_id}: {e}")
        return None

def generate_followup_content(original_email_body, brand_name, poc_name):
    """Generates follow-up email content using Gemini."""
    
    prompt = f"""
    # Role
    You are Bhargav Kulkarni, a persistent but polite Business Development Representative for NoBrokerHood.

    # Goal
    Write a very short (3-4 sentences) follow-up email to a brand POC who hasn't replied to your first email about advertising on NoBrokerHood.

    # Context
    - Brand: {brand_name}
    - POC Name: {poc_name}
    - You previously sent them this email:
    "{original_email_body}"
    - They have not replied.
    - You are replying to the same thread.

    # Instructions
    1. **Tone:** Friendly, casual, "floating this to the top".
    2. **Content:**
        - Acknowledge they are busy.
        - Reiterate the value in 2 sentence (connecting with residents for Christmas and New Year).
        - Ask for a quick 10-min chat.
    3. **Subject Line:** Generate a **creative and eye-catching** subject line.
        - **STRICTLY FORBIDDEN:** Do NOT use words like "Follow up", "Follow-up", "Checking in", "Quick", "Bump", "Just", or "Festival".
        - **GOAL:** Create curiosity or highlight value. It should feel like a fresh idea, not a nag.
        - **Examples:** "Residents are waiting?", "Missed connection?", "10 mins for [Brand]?", "Idea for [Brand]", "Regarding [Topic]".
    4. **No Fluff:** Do not use "I hope this email finds you well". Start directly.
    5. **Output:** Return ONLY a JSON object with keys "email_body" and "email_subject". Do not return markdown formatting.
    
    Example Output:
    {{
        "email_body": "Hi [Name], just floating this to the top..."
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        if response.text:
            data = json.loads(response.text)
            return data.get("email_body"), data.get("email_subject")
        return None, None
    except Exception as e:
        print(f"❌ Gemini generation error: {e}")
        return None, None

def send_reply(service, to_email, thread_id, message_id, body_text, subject, signature_path=None):
    """Sends a reply to an existing thread with HTML support and signature."""
    try:
        message = EmailMessage()
        message['To'] = to_email
        message['Subject'] = subject
        # Threading headers
        message['References'] = message_id
        message['In-Reply-To'] = message_id
        
        # Construct HTML Body with Signature
        body_html = body_text.replace("\n", "<br>")
        
        # Add Signature HTML
        # - Horizontal line
        # - Image (width=72)
        # - Text formatted
        signature_html = """
        <br><br>
        <hr>
        <p><img src="cid:signature_image" alt="NoBrokerHood" width="72"></p>
        <p><strong>Bhargav Kulkarni</strong><br>
        Brand Partnerships & Alliances<br>
        <a href="tel:+918618818322" style="color: #0066cc; text-decoration: none;">+91 8618818322</a> | NoBrokerHood</p>
        """
        full_html = body_html + signature_html
        
        # Set content
        message.set_content(body_text + "\n\n--\nBhargav Kulkarni\nBrand Partnerships & Alliances\n+91 8618818322 | NoBrokerHood") # Fallback text
        message.add_alternative(full_html, subtype='html')
        
        # Attach Signature Image
        if signature_path and os.path.exists(signature_path):
            with open(signature_path, 'rb') as f:
                img_data = f.read()
            message.get_payload()[1].add_related(img_data, maintype='image', subtype='gif', cid='signature_image', filename='signature.gif')

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        create_message = {
            'raw': encoded_message,
            'threadId': thread_id
        }
    
        sent_message = service.users().messages().send(userId="me", body=create_message).execute()
        return sent_message
    except HttpError as error:
        print(f"❌ An error occurred sending email: {error}")
        return None

def main():
    creds = get_google_creds()
    gmail_service = build('gmail', 'v1', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    
    # Signature Path
    signature_path = os.path.join(os.path.dirname(__file__), 'unnamed.gif')

    # 1. Read Sheet Data
    print("Reading sheet data...")
    rows = get_sheet_data(sheets_service, SPREADSHEET_ID, f"{SHEET_NAME}!A:AB") # Read up to AB to check for existing followups
    
    if not rows:
        print("No data found.")
        return

    headers = rows[0]
    # Map headers to indices
    try:
        idx_reply = headers.index("Reply (T/F)")
        idx_uuid = headers.index("Email UUID")
        idx_email = headers.index("Email")
        idx_brand = headers.index("Company / Brand Name")
        idx_poc = headers.index("Client POC Name")
        
        # Check if Followup columns exist, if not, we will append
        if "Followup UUID" in headers:
            idx_followup_uuid = headers.index("Followup UUID")
        else:
            idx_followup_uuid = len(headers) # Will be new column
            
        if "Followup Sent" in headers:
            idx_followup_sent = headers.index("Followup Sent")
        else:
            idx_followup_sent = len(headers) + 1 # Will be new column

    except ValueError as e:
        print(f"❌ Missing required column: {e}")
        return

    # Add headers if they don't exist (visually in console, logic handles indices)
    print(f"Processing {len(rows)-1} rows...")

    count = 0
    for i, row in enumerate(rows[1:], start=2): # start=2 because sheet is 1-indexed and we skip header
        
        # Safety check for row length
        if len(row) <= idx_reply: continue
        
        reply_status = row[idx_reply]
        email_uuid = row[idx_uuid] if len(row) > idx_uuid else ""
        
        # Check if already followed up
        followup_sent = "False"
        if len(row) > idx_followup_sent:
            followup_sent = row[idx_followup_sent]
        elif len(row) > idx_followup_uuid and row[idx_followup_uuid]: # Fallback check
             followup_sent = "True"

        # CRITERIA: No Reply AND No Follow-up sent AND We have an original UUID
        # Normalize to string and uppercase for comparison
        reply_str = str(reply_status).upper()
        followup_str = str(followup_sent).upper()
        
        if reply_str == "FALSE" and followup_str != "TRUE" and email_uuid:
            
            brand_name = row[idx_brand]
            poc_name = row[idx_poc]
            to_email = row[idx_email]

            print(f"\nProcessing Row {i}: {brand_name} ({to_email})")
            
            # 1. Fetch Original Email
            original_body = get_email_body(gmail_service, email_uuid)
            if not original_body:
                print("   Skipping: Could not fetch original email body.")
                continue

            # 2. Generate Content
            print("   Generating content...")
            followup_body, followup_subject = generate_followup_content(original_body, brand_name, poc_name)
            if not followup_body:
                print("   Skipping: Failed to generate content.")
                continue
            
            print(f"   📝 Subject: {followup_subject}")
            print(f"   📝 Body: {followup_body.replace(chr(10), ' ')[:100]}...")

            # 3. Send Reply
            print("   Sending email...")
            try:
                msg_details = gmail_service.users().messages().get(userId='me', id=email_uuid).execute()
                thread_id = msg_details['threadId']
                
                # Use generated subject if available, else fallback to original subject logic
                final_subject = followup_subject if followup_subject else "Follow-up"

                sent_msg = send_reply(gmail_service, to_email, thread_id, email_uuid, followup_body, final_subject, signature_path)
                
                if sent_msg:
                    new_id = sent_msg['id']
                    print(f"   ✅ Sent! ID: {new_id}")
                    
                    # 4. Update Sheet
                    # We need to write to specific columns. 
                    # Assuming standard grid, we calculate column letters.
                    # Helper to convert index to letter (0 -> A, 26 -> AA)
                    def col_letter(n):
                        string = ""
                        while n >= 0:
                            string = chr((n % 26) + 65) + string
                            n = (n // 26) - 1
                        return string

                    col_uuid = col_letter(26) # AA
                    col_sent = col_letter(27) # AB
                    
                    # Update Followup UUID
                    update_sheet_cell(sheets_service, SPREADSHEET_ID, f"{SHEET_NAME}!{col_uuid}{i}", new_id)
                    # Update Followup Sent
                    update_sheet_cell(sheets_service, SPREADSHEET_ID, f"{SHEET_NAME}!{col_sent}{i}", "True")
                    
                    count += 1
                    time.sleep(2) # Rate limit safety
                else:
                    print("   ❌ Failed to send.")
            
            except Exception as e:
                print(f"   ❌ Error in processing: {e}")

            if count >= 10: # Safety break for testing
                print("Stopped after 10 emails for safety.")
                break
        else:
            # Debug: Print why it skipped
            print(f"Row {i} Skipped: Reply='{reply_status}', Followup='{followup_sent}', UUID='{email_uuid}'")

if __name__ == "__main__":
    main()
