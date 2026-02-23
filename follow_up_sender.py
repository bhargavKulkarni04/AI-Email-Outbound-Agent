
import os
import time
import re # Import regex for signature stripping
import base64
import json
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.message import EmailMessage
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables from .env file in the script's directory
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path=dotenv_path)

# Configuration
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    'https://www.googleapis.com/auth/spreadsheets',
]
SPREADSHEET_ID = "1wSQh-5DXBAD0W2-9Blg1RtQ4berwnBcKnVAlxZLrlxU" # bhargav sheet id
SHEET_NAME = "Sheet7"

# --- File & API Key Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_PATH = os.path.join(BASE_DIR, "token.json")
CLIENT_SECRET_PATH = os.path.join(BASE_DIR, "client_secret.json")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize Gemini Client
try:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found. Make sure it's in your .env file.")
    client = genai.Client(api_key=GEMINI_API_KEY)
    print("✅ Gemini model configured successfully.")
except Exception as e:
    print(f"❌ Error configuring Gemini API: {e}")
    exit()

def strip_gemini_signature(text):
    """
    Removes common email signature patterns and specific unwanted text from Gemini's output.
    """
    if not isinstance(text, str):
        return ""
        
    signature_patterns = [
        r"Best regards,.*", r"Sincerely,.*", r"Best,.*", r"Thanks,.*",
        r"Regards,.*", r"Warmly,.*", r"Kind regards,.*",
        r"here in side quotes text.*", # Specific pattern from user's example
        r"Bhargav Kulkarni.*", # Catching the name directly if it appears
        r"Brand Partnerships & Alliances.*",
        r"\+\d{1,3}\s?\d{10,12}.*", # Phone number pattern
        r"NoBrokerHood.*",
        r"---", # Common separator
        r"__", # Common separator
    ]
    
    cleaned_text = text
    for pattern in signature_patterns:
        cleaned_text = re.sub(pattern, "", cleaned_text, flags=re.IGNORECASE | re.DOTALL).strip()
    return cleaned_text

def get_unique_headers(header_row):
    """Processes a header row to make all column names unique."""
    seen = {}
    new_headers = []
    for col in header_row:
        original_col = col.strip()
        if not original_col: # Handle empty header cells
            new_headers.append(f"Unknown_Column_{len(new_headers)}")
            continue
        if original_col in seen:
            seen[original_col] += 1
            new_headers.append(f"{original_col}_{seen[original_col]}")
        else:
            seen[original_col] = 0
            new_headers.append(original_col)
    return new_headers

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

def generate_followup_content(original_email_body, brand_name, poc_name, case_studies):
    """Generates follow-up email content using Gemini."""
    
    prompt = f"""
    # Role
    You are Bhargav Kulkarni, a sharp and helpful Business Development Representative for NoBrokerHood. Your follow-ups are valuable and always provide a new piece of information.

    # Goal
    Write a personalized, value-driven follow-up email that is roughly twice as long as a simple reminder. The goal is to build credibility by showing a relevant success story and re-engage the contact for a meeting.

    # Context
    - Brand: {brand_name}
    - POC Name: {poc_name}
    - You are replying in the same thread. The original email you sent was:
    "{original_email_body}"
    - They have not replied.
    - Here are some relevant case studies you can use to add value:
    <CASE_STUDIES>
    {case_studies}
    </CASE_STUDIES>

    # Instructions
    1. **Tone:** Confident, professional, and helpful. You are sharing a relevant insight, not just asking for their time.
    2. **Content:**
        - Start with a direct and polite opening.
        - **Crucially, pick ONE relevant case study from the <CASE_STUDIES> provided.** Mention the brand by name and their success (e.g., "We recently helped [Case Study Brand] achieve [ROI] by using [NBH services used]."). This is the core of the email.
        - Connect that success back to {brand_name}, suggesting they could see similar results.
        - Keep the email concise, around 3-4 sentences.
        - End with a clear, low-friction call to action for a brief chat.
    3. **Subject Line:** Generate a **professional and intriguing** subject line.
        - **STRICTLY FORBIDDEN:** Do NOT use "Follow up", "Checking In", or "Touching base".
        - **GOAL:** Spark curiosity by hinting at the new information.
        - **Excellent Examples:** "A thought for {brand_name}", "Quick question", "Idea for your holiday campaigns", "How [Case Study Brand] reached our residents".
    4. **Strictly Avoid:** Do not use weak or apologetic language like "Hope you're doing well," "Sorry to bother you," or "In case you missed it."
    5. **No Signature:** Do not add any sign-off like "Best regards" or your name. The script handles the signature.
    6. **Output:** Return ONLY a JSON object with keys "email_body" and "email_subject". Do not return markdown formatting.
    
    Example Output:
    {{
        "email_body": "Hi {poc_name},\\n\\nCircling back on this with a quick thought. We recently helped Audi generate over 22,000 clicks with a 3% CTR using our in-app banners.\\n\\nGiven your focus on the premium market, I believe a similar campaign could drive significant interest for {brand_name}.\\n\\nAre you free for a 10-minute chat next week to explore?",
        "email_subject": "How Audi reached our residents"
    }}
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        if response.text:
            data = json.loads(response.text)
            body = data.get("email_body")
            subject = data.get("email_subject")
            cleaned_body = strip_gemini_signature(body) # Clean the body
            return cleaned_body, subject
        return None, None
    except Exception as e:
        print(f"Gemini generation error: {e}")
        return None, None
def send_reply(service, to_email, thread_id, message_id, body_text, subject, signature_path=None):
    """Sends a reply to an existing thread with HTML support and signature."""
    try:
        message = EmailMessage()
        message['To'] = to_email
        message['Subject'] = subject
        message['Bcc'] = "" # Explicitly set BCC to empty to override Gmail settings
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
        print(f" An error occurred sending email: {error}")
        return None

def main():
    creds = get_google_creds()
    gmail_service = build('gmail', 'v1', credentials=creds)
    sheets_service = build('sheets', 'v4', credentials=creds)
    
    # Signature Path
    signature_path = os.path.join(BASE_DIR, 'unnamed.gif')

    # Load Case Studies
    with open(os.path.join(BASE_DIR, "case_studies.json"), "r", encoding="utf-8") as f:
        all_case_studies = json.load(f)

    # 1. Read Sheet Data
    print("Reading sheet data from Sheet7...")
    rows = get_sheet_data(sheets_service, SPREADSHEET_ID, f"{SHEET_NAME}!A:AD") # Read up to AD
    
    if not rows:
        print("No data found.")
        return

    # Process headers to be unique
    headers = get_unique_headers(rows[0])
    
    # Map headers to indices
    try:
        # Use the first occurrence for initial reply check
        idx_reply = headers.index("Reply (T/F)") 
        idx_uuid = headers.index("Email UUID")
        idx_email = headers.index("Email")
        idx_brand = headers.index("Company / Brand Name")
        idx_poc = headers.index("Client POC Name")
        idx_errors = headers.index("Errors")
        idx_industry1 = headers.index("top1_industry")
        idx_industry2 = headers.index("top2_industry")
        idx_wrong_mail = headers.index("Wrong mail id msg")
        idx_followup_uuid = headers.index("Follow-up UUID")
        idx_followup_sent = headers.index("Follow up sent")
        
        # The columns to update for the follow-up's own reply status
        # These are the *second* occurrences of these names
        idx_followup_reply_status = headers.index("Reply (T/F)_1")
        idx_followup_reply_snippet = headers.index("Reply snippet_1")

        print("✅ All required columns found.")

    except ValueError as e:
        print(f" Missing required column: {e}")
        return

    # Add headers if they don't exist (visually in console, logic handles indices)
    print(f"Processing {len(rows)-1} rows...")

    count = 0
    for i, row in enumerate(rows[1:], start=2): # start=2 because sheet is 1-indexed and we skip header
        
        # Safety check for row length
        # Pad row with empty strings if it's shorter than headers
        num_missing_cols = len(headers) - len(row)
        if num_missing_cols > 0:
            row.extend([''] * num_missing_cols)
        
        reply_status = row[idx_reply]
        email_uuid = row[idx_uuid] if len(row) > idx_uuid else ""
        error_msg = row[idx_errors] if len(row) > idx_errors else ""
        wrong_mail_msg = row[idx_wrong_mail] if len(row) > idx_wrong_mail else ""
        
        # Check if already followed up
        followup_sent = "False"
        if len(row) > idx_followup_sent:
            followup_sent = row[idx_followup_sent]
        elif len(row) > idx_followup_uuid and row[idx_followup_uuid]: # Fallback check
             followup_sent = "True"

        # CRITERIA: No Reply AND No Follow-up AND No Errors AND We have a UUID
        # Normalize to string and uppercase for comparison
        reply_str = str(reply_status).upper()
        followup_str = str(followup_sent).upper()
        
        if reply_str == "FALSE" and followup_str != "TRUE" and email_uuid and not error_msg and not wrong_mail_msg:
            
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
            
            # Find relevant case studies for the contact's industry
            industry = row[idx_industry1]
            if not industry or industry == 'Other / Unknown':
                industry = row[idx_industry2]
            
            relevant_case_studies = [cs for cs in all_case_studies if cs.get("Industry") == industry]
            case_studies_text = json.dumps(relevant_case_studies, indent=2) if relevant_case_studies else "No specific case studies found for this industry."

            followup_body, followup_subject = generate_followup_content(original_body, brand_name, poc_name, case_studies_text)
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
                    # Dynamically find column letters from their indices
                    def col_letter(n):
                        string = ""
                        while n >= 0:
                            string = chr((n % 26) + 65) + string
                            n = (n // 26) - 1
                        return string
                    
                    col_uuid = col_letter(idx_followup_uuid)
                    col_sent = col_letter(idx_followup_sent)
                    
                    # Update Followup UUID
                    update_sheet_cell(sheets_service, SPREADSHEET_ID, f"{SHEET_NAME}!{col_uuid}{i}", new_id)
                    # Update Followup Sent
                    update_sheet_cell(sheets_service, SPREADSHEET_ID, f"{SHEET_NAME}!{col_sent}{i}", "True")
                    # Also update the follow-up's own reply status columns
                    col_followup_reply_status = col_letter(idx_followup_reply_status)
                    col_followup_reply_snippet = col_letter(idx_followup_reply_snippet)
                    update_sheet_cell(sheets_service, SPREADSHEET_ID, f"{SHEET_NAME}!{col_followup_reply_status}{i}", "Awaiting Reply")
                    
                    count += 1
                    time.sleep(2) # Rate limit safety
                else:
                    print("    Failed to send.")
            
            except Exception as e:
                print(f"    Error in processing: {e}")

            if count >= 10: # Safety break for testing
                print("Stopped after 10 emails for safety.")
                break
        else:
            # Debug: Print why it skipped
            print(f"Row {i} Skipped: Reply='{reply_status}', Followup='{followup_sent}', UUID='{bool(email_uuid)}', Error='{bool(error_msg)}', Bounce='{bool(wrong_mail_msg)}'")

if __name__ == "__main__":
    main()
