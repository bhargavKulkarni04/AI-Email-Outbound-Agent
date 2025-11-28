import os
import re
import base64
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import settings from the central config file
import config


def get_google_creds():
    """Handles Google API authentication flow."""
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

def get_header(headers, name):
    """Extracts a specific header value from a list of email headers."""
    for header in headers:
        if header['name'].lower() == name.lower():
            return header['value']
    return None

def parse_email_address(header_value):
    """Extracts just the email address from a 'To' or 'From' header."""
    if not header_value:
        return None
    match = re.search(r'<(.+?)>', header_value)
    if match:
        return match.group(1).lower().strip()
    return header_value.strip().lower()

def decode_message_part(part):
    """Decodes a single part of an email message body."""
    body_data = part.get('body', {}).get('data')
    if not body_data:
        return ""
    
    decoded_bytes = base64.urlsafe_b64decode(body_data)
    charset = 'utf-8'
    
    for header in part.get('headers', []):
        if header['name'].lower() == 'content-type':
            ct_match = re.search(r'charset="?([^"]+)"?', header['value'])
            if ct_match:
                charset = ct_match.group(1)
                break
                
    try:
        return decoded_bytes.decode(charset, errors='replace')
    except (UnicodeDecodeError, LookupError):
        return decoded_bytes.decode('latin-1', errors='replace')

def get_email_body(message_payload):
    """Extracts the text body from an email message payload."""
    body = ""
    if 'parts' in message_payload:
        for part in message_payload['parts']:
            if part['mimeType'] == 'text/plain':
                body += decode_message_part(part)
            elif 'parts' in part and part['mimeType'].startswith('multipart/'):
                body += get_email_body(part)
    elif message_payload.get('mimeType') == 'text/plain':
        body += decode_message_part(message_payload)
        
    return body.strip()

def is_bounce_message(message):
    """Checks if a message is a bounce notification."""
    headers = message['payload']['headers']
    from_header = get_header(headers, 'From')
    subject_header = get_header(headers, 'Subject')

    if not from_header or not subject_header:
        return False

    from_address = from_header.lower()
    subject = subject_header.lower()

    if "mailer-daemon" in from_address or "mail delivery subsystem" in from_address:
        return True
    
    if any(keyword in subject for keyword in ["address not found", "undeliverable", "delivery status notification", "mail delivery failed"]):
        return True

    return False

def extract_bounce_reason(body):
    """Extracts the SMTP error message from a bounce email body."""
    smtp_match = re.search(r'\b(5\d{2}(\s5\.\d\.\d{1,2})?)\s.*', body, re.IGNORECASE | re.DOTALL)
    if smtp_match:
        return smtp_match.group(0).split('\n')[0].strip()
    
    reason_match = re.search(r'address not found|user unknown|no such user', body, re.IGNORECASE)
    if reason_match:
        return reason_match.group(0).strip()

    return "Could not automatically extract bounce reason."

def contains_signature(body_text):
    """Checks if the email body contains any of the signature markers."""
    body_lower = body_text.lower()
    return any(marker in body_lower for marker in config.SIGNATURE_MARKERS)

# =========================================================
# =  MAIN SCRIPT LOGIC
# =========================================================

def main():
    """Main function to track replies and bounces."""
    print("Starting reply tracker...")
    
    try:
        creds = get_google_creds()
        gmail_service = build("gmail", "v1", credentials=creds)
        sheets_service = build("sheets", "v4", credentials=creds)
        print("Successfully authenticated with Google APIs.")
    except Exception as e:
        print(f"Error during authentication: {e}")
        return

    try:
        sheet_range = f"{config.REPLY_TRACKER_SHEET_NAME}!A:Z"
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=config.SPREADSHEET_ID, range=sheet_range).execute()
        values = result.get('values', [])
        
        if not values:
            print("No data found in the spreadsheet.")
            return

        headers = values[0]
        header_map = {header.strip(): i for i, header in enumerate(headers)}
        
        required_headers = ['Email', 'Reply (T/F)', 'Reply snippet', 'Wrong mail id msg', 'Errors', 'sent by']
        for h in required_headers:
            if h not in header_map:
                print(f"Error: Missing required header '{h}' in the sheet. Please add it and try again.")
                return

        email_to_row_map = {row[header_map['Email']].lower().strip(): i + 1 for i, row in enumerate(values) if len(row) > header_map['Email'] and row[header_map['Email']]}
        print(f"Loaded {len(email_to_row_map)} emails from the Google Sheet.")

    except HttpError as e:
        print(f"Error accessing Google Sheet: {e}")
        return

    query = "in:sent newer_than:8d"
    try:
        sent_messages = []
        page_token = None
        while True:
            response = gmail_service.users().messages().list(
                userId='me',
                q=query,
                pageToken=page_token
            ).execute()
            
            messages = response.get('messages', [])
            sent_messages.extend(messages)
            
            page_token = response.get('nextPageToken')
            if not page_token:
                break
        
        print(f"Found {len(sent_messages)} sent emails from the last 15 days to process.")
    except HttpError as e:
        print(f"Error fetching emails from Gmail: {e}")
        return

    updates_to_perform = []
    checked_count = 0
    reply_count = 0
    bounce_count = 0
    no_reply_count = 0
    
    processed_threads = set()

    for msg_summary in sent_messages:
        try:
            thread_id = msg_summary['threadId']

            if thread_id in processed_threads:
                continue
            processed_threads.add(thread_id)
            
            thread_response = gmail_service.users().threads().get(userId='me', id=thread_id, format='full').execute()
            thread_messages = thread_response['messages']
            
            sent_msg = thread_messages[0] 
            checked_count += 1
            
            sent_headers = sent_msg['payload']['headers']
            to_email = parse_email_address(get_header(sent_headers, 'To'))
            
            if not to_email or to_email not in email_to_row_map:
                continue

            row_num = email_to_row_map[to_email]
            sent_timestamp_ms = int(sent_msg['internalDate'])
            
            update_data = {
                'reply': False, 'snippet': "",
                'bounce_msg': "", 'error': ""
            }

            bounce_found = False
            reply_found = False

            for message in sorted(thread_messages, key=lambda m: int(m['internalDate'])):
                msg_timestamp_ms = int(message['internalDate'])
                if msg_timestamp_ms <= sent_timestamp_ms:
                    continue

                msg_headers = message['payload']['headers']
                from_header = get_header(msg_headers, 'From')
                from_email = parse_email_address(from_header)
                
                if is_bounce_message(message):
                    bounce_body = get_email_body(message['payload'])
                    bounce_reason = extract_bounce_reason(bounce_body)
                    update_data['bounce_msg'] = bounce_reason # No name appended
                    bounce_count += 1
                    bounce_found = True
                    break 

                if from_email and from_email != to_email:
                    reply_body = get_email_body(message['payload'])
                    update_data['reply'] = True
                    update_data['snippet'] = reply_body[:200]
                    if contains_signature(reply_body):
                         update_data['bounce_msg'] = config.SIGNATURE_TAG
                    reply_count += 1
                    reply_found = True
                    break 
            
            if not bounce_found and not reply_found:
                no_reply_count += 1

            updates_to_perform.append((row_num, update_data))

        except HttpError as e:
            print(f"Error processing thread {msg_summary.get('threadId', 'N/A')}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred for thread {msg_summary.get('threadId', 'N/A')}: {e}")

    if updates_to_perform:
        print(f"Preparing to update {len(updates_to_perform)} rows in the sheet...")
        
        # Break updates into smaller chunks to avoid network errors
        chunk_size = 100 
        for i in range(0, len(updates_to_perform), chunk_size):
            chunk = updates_to_perform[i:i + chunk_size]
            batch_update_data = []
            print(f"Processing chunk {i//chunk_size + 1}...")

            for row_num, data in chunk:
                batch_update_data.extend([
                    {'range': f"{config.REPLY_TRACKER_SHEET_NAME}!{chr(ord('A') + header_map['Reply (T/F)'])}{row_num}", 'values': [[data['reply']]]},
                    {'range': f"{config.REPLY_TRACKER_SHEET_NAME}!{chr(ord('A') + header_map['Reply snippet'])}{row_num}", 'values': [[data['snippet']]]},
                    {'range': f"{config.REPLY_TRACKER_SHEET_NAME}!{chr(ord('A') + header_map['Wrong mail id msg'])}{row_num}", 'values': [[data['bounce_msg']]]},
                    {'range': f"{config.REPLY_TRACKER_SHEET_NAME}!{chr(ord('A') + header_map['Errors'])}{row_num}", 'values': [[data['error']]]},
                    {'range': f"{config.REPLY_TRACKER_SHEET_NAME}!{chr(ord('A') + header_map['sent by'])}{row_num}", 'values': [["Bhargav"]]}
                ])
            
            try:
                body = {'valueInputOption': 'USER_ENTERED', 'data': batch_update_data}
                sheets_service.spreadsheets().values().batchUpdate(
                    spreadsheetId=config.SPREADSHEET_ID, body=body).execute()
                print(f"Successfully updated chunk {i//chunk_size + 1}.")
            except HttpError as e:
                print(f"Error updating Google Sheet chunk: {e}")
            except Exception as e:
                print(f"An unexpected error occurred during sheet update: {e}")

    print("\n" + "="*50)
    print("                      SUMMARY")
    print("="*50)
    print(f"Checked {checked_count} sent mails | Replies: {reply_count} | Bounces: {bounce_count} | No Reply: {no_reply_count}")
    print("="*50)
    print("Script finished.")

if __name__ == '__main__':
    main()