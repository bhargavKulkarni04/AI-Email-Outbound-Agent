
"""
Phase 2: High-Impact Follow-up Outreach
========================================
This is the MAIN file. Run this to process leads and send follow-ups.

How it works:
1. Reads Meeting_data sheet for qualified leads (Conducted + >=10 mins + Not Closed).
2. Opens each lead's Google Doc transcript.
3. Gemini 2.5 Flash generates MOM + Follow-up email.
4. Nano Banna Pro generates a custom brand mockup.
5. Sends the complete HTML package to the client with CC to team.
"""

import time
import uuid
from datetime import datetime
import config
import google_auth
import read_transcript
import generate_email
import generate_image
import send_email

# --- Safety Settings ---
DELAY_BETWEEN_EMAILS = 5      # Seconds between each email
MAX_EMAILS_PER_RUN = 400      # Set low for testing, change to 500 for production
CC_EMAIL = "brand.vmeet@nobroker.in"  # Team CC for visibility

# --- Test Mode ---
# Set to True to send ALL emails to your own inbox instead of clients
TEST_MODE = False
TEST_EMAIL = "bhargav.s@nobroker.in"


def col_idx_to_letter(idx):
    """Converts a 0-based column index to Excel-style letters (A, B... Z, AA, AB...)."""
    letter = ""
    while idx >= 0:
        letter = chr(65 + (idx % 26)) + letter
        idx = (idx // 26) - 1
    return letter


def find_column(headers, keyword):
    """Finds a column index by matching a keyword in the header name."""
    for i, h in enumerate(headers):
        if keyword.lower() in h.lower():
            return i
    return None


def main():
    # Step 1: Login to Google
    print("[AUTH] Logging in to Google...")
    services = google_auth.get_services()

    # Step 2: Read the sheet
    print(f"[SHEET] Reading {config.MEETING_DATA_SHEET}...")
    result = services["sheets"].spreadsheets().values().get(
        spreadsheetId=config.SPREADSHEET_ID,
        range=f"{config.MEETING_DATA_SHEET}!A:CF"
    ).execute()

    rows = result.get("values", [])
    if not rows:
        print("[ERROR] No data found.")
        return

    headers = [h.strip() for h in rows[0]]
    print(f"[DEBUG] Found {len(headers)} columns.")

    # Find column positions
    idx_brand = find_column(headers, "Brand Name")
    idx_dur = find_column(headers, "Meeting duration")
    idx_done = find_column(headers, "Meeting Done")
    idx_cls = find_column(headers, "Closure Status")
    idx_doc = find_column(headers, "Transcript Link")
    idx_attendees = find_column(headers, "Client Attendees")
    idx_email_uuid = find_column(headers, "Email UUID")
    idx_date = find_column(headers, "Meeting Date")
    idx_sent = find_column(headers, "Email Sent (T/F)")
    idx_reply = find_column(headers, "Reply (T/F)")
    idx_snippet = find_column(headers, "Reply snippet")
    idx_title = find_column(headers, "Meeting Title")
    idx_industry = find_column(headers, "Industry")

    # Audit Columns
    idx_is_before_dec = find_column(headers, "is_before_dec")
    idx_is_greater_10 = find_column(headers, "is_greater_10")
    idx_is_conducted = find_column(headers, "is_meeting_conducted")
    idx_not_closed = find_column(headers, "not_closed")

    if None in (idx_brand, idx_dur, idx_done, idx_cls, idx_doc, idx_attendees, idx_is_before_dec, idx_is_greater_10, idx_is_conducted, idx_not_closed):
        print("[ERROR] Could not find required audit columns.")
        print(f"DEBUG: idx_brand={idx_brand}, idx_dur={idx_dur}, idx_is_before_dec={idx_is_before_dec}")
        return
    
    print(f"[DEBUG] Processing first {MAX_EMAILS_PER_RUN} qualifying leads...")

    # Step 3: Process each qualified lead
    sent_count = 0
    skipped_count = 0

    for i, row in enumerate(rows[1:], start=2):
        while len(row) < len(headers):
            row.append("")

        # --- AUDIT DOUBLE-CHECK ---
        is_before_dec = row[idx_is_before_dec].strip().upper() == "TRUE"
        is_greater_10 = row[idx_is_greater_10].strip().upper() == "TRUE"
        is_conducted = row[idx_is_conducted].strip().upper() == "TRUE"
        not_closed = row[idx_not_closed].strip().upper() == "TRUE"

        # All conditions must be MET for the row to be processed
        if not (is_before_dec and is_greater_10 and is_conducted and not_closed):
            if i <= 7: # Only print debug for the first few rows
                print(f"   [DEBUG] Row {i} skipped by audit check.")
            continue

        # --- DUPLICATE PROTECTION ---
        # Skip if Email UUID is already populated (means we already sent it)
        if idx_email_uuid is not None and row[idx_email_uuid].strip():
            skipped_count += 1
            print(f"   [SKIP] Row {i} already has a UUID (sent before).")
            continue

        brand = row[idx_brand]
        doc_url = row[idx_doc]
        attendees_raw = row[idx_attendees]
        industry = row[idx_industry] if idx_industry is not None else None

        print(f"\n{'='*50}")
        print(f"[LEAD #{sent_count+1}] {brand} (Row {i})")

        # Step 3a: Read transcript
        print("[TRANSCRIPT] Reading...")
        transcript = read_transcript.read_doc(services["docs"], doc_url)
        if not transcript:
            print("   [SKIP] No transcript found.")
            continue
        
        print(f"   [INFO] Transcript read successfully. Length: {len(transcript)} chars.")
        print(f"   [PREVIEW] {transcript[:100]}...")

        # Step 3b: Generate email + image prompt (with retry if image_prompt missing)
        print("[GEMINI] Generating MOM and follow-up...")
        email_data = None
        for gen_attempt in range(1, 4):  # 3 retries
            email_data = generate_email.generate(brand, attendees_raw, transcript, industry=industry)
            if not email_data:
                print(f"   [SKIP] Gemini could not generate content (attempt {gen_attempt}/3).")
                time.sleep(5)
                continue
            if "image_prompt" in email_data and email_data["image_prompt"]:
                break  # Got everything, move on
            else:
                print(f"   [RETRY {gen_attempt}/3] image_prompt missing. Retrying in 5s...")
                time.sleep(5)
        
        if not email_data or "image_prompt" not in email_data:
            print(f"   [SKIP] Could not get image_prompt for {brand} after 3 attempts. Skipping.")
            continue

        # Step 3c: Generate mockup image
        print(f"[IMAGE] Generating mockup for {brand}...")
        mockup = generate_image.create_mockup(brand, email_data["image_prompt"])

        # Step 3d: Send email
        to_emails = send_email.parse_attendees(attendees_raw)
        if not to_emails:
            print("   [SKIP] No client email found.")
            continue

        # --- Test Mode Override ---
        meeting_title = row[idx_title] if idx_title is not None else brand
        
        # Use the single subject generated by Gemini
        subject = email_data.get("subject", f"Follow up: {brand}")

        if TEST_MODE:
            to_emails = TEST_EMAIL if isinstance(TEST_EMAIL, list) else [TEST_EMAIL]
            cc_to_use = None
            print(f"[TEST MODE] Redirecting to {to_emails}")
            print(f"   Original meeting: {meeting_title}")
        else:
            cc_to_use = CC_EMAIL

        print(f"[SEND] To: {to_emails}")
        sent_id = send_email.send(
            gmail_service=services["gmail"],
            to_emails=to_emails,
            subject=subject,
            email_body=email_data["email_body"],
            mockup_bytes=mockup,
            cc=cc_to_use
        )

        if sent_id:
            sent_count += 1
            
            # --- Update Google Sheet Status ---
            print(f"[SHEET] Updating status for {brand}...")
            new_uuid = str(uuid.uuid4())
            
            # Prepare batch update
            batch_data = []
            
            if idx_email_uuid is not None:
                batch_data.append({
                    'range': f"{config.MEETING_DATA_SHEET}!{col_idx_to_letter(idx_email_uuid)}{i}",
                    'values': [[new_uuid]]
                })
                
            if idx_sent is not None:
                batch_data.append({
                    'range': f"{config.MEETING_DATA_SHEET}!{col_idx_to_letter(idx_sent)}{i}",
                    'values': [["True"]]
                })
                
            if idx_reply is not None:
                batch_data.append({
                    'range': f"{config.MEETING_DATA_SHEET}!{col_idx_to_letter(idx_reply)}{i}",
                    'values': [["False"]]
                })

            if idx_snippet is not None:
                batch_data.append({
                    'range': f"{config.MEETING_DATA_SHEET}!{col_idx_to_letter(idx_snippet)}{i}",
                    'values': [[""]]
                })

            if batch_data:
                services["sheets"].spreadsheets().values().batchUpdate(
                    spreadsheetId=config.SPREADSHEET_ID,
                    body={
                        "valueInputOption": "USER_ENTERED",
                        "data": batch_data
                    }
                ).execute()

            print(f"[SUCCESS] Row {i} updated with UUID and Sent status.")
            print(f"[WAIT] {DELAY_BETWEEN_EMAILS}s before next email...")
            time.sleep(DELAY_BETWEEN_EMAILS)
        else:
            print("   [FAIL] Email failed to send. Moving to next lead.")

        # Hard stop at max limit
        if sent_count >= MAX_EMAILS_PER_RUN:
            print(f"\n[LIMIT] Reached {MAX_EMAILS_PER_RUN} email limit. Stopping.")
            break

    print(f"\n{'='*50}")
    print(f"[DONE] {sent_count} follow-ups sent. {skipped_count} duplicates skipped.")
    print(f"{'='*50}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[FATAL ERROR] {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("--- Execution complete. ---")
