
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
import config
import google_auth
import read_transcript
import generate_email
import generate_image
import send_email

# --- Safety Settings ---
DELAY_BETWEEN_EMAILS = 5      # Seconds between each email
MAX_EMAILS_PER_RUN = 5        # Set low for testing, change to 500 for production
CC_EMAIL = "brand.vmeet@nobroker.in"  # Team CC for visibility

# --- Test Mode ---
# Set to True to send ALL emails to your own inbox instead of clients
TEST_MODE = True
TEST_EMAIL = "bhargav.s@nobroker.in"


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

    # Find column positions
    idx_brand = find_column(headers, "Brand Name")
    idx_dur = find_column(headers, "Meeting duration")
    idx_done = find_column(headers, "Meeting Done")
    idx_cls = find_column(headers, "Closure Status")
    idx_doc = find_column(headers, "Transcript Link")
    idx_attendees = find_column(headers, "Client Attendees")
    idx_email_uuid = find_column(headers, "Email UUID")
    idx_title = find_column(headers, "Meeting Title")
    idx_industry = find_column(headers, "Industry")

    if None in (idx_brand, idx_dur, idx_done, idx_cls, idx_doc, idx_attendees):
        print("[ERROR] Could not find required columns.")
        return

    # Step 3: Process each qualified lead
    sent_count = 0
    skipped_count = 0

    for i, row in enumerate(rows[1:], start=2):
        while len(row) < len(headers):
            row.append("")

        if i < 5:  # Temporary skip to start from 4th lead (row 5)
            continue

        # Apply filters
        try:
            duration = float(row[idx_dur].strip() or 0)
        except:
            duration = 0

        done = row[idx_done].strip().lower()
        closure = row[idx_cls].strip().lower()

        if done != "conducted" or "close" in closure or duration < config.MIN_MEETING_DURATION:
            continue

        brand = row[idx_brand]
        doc_url = row[idx_doc]
        attendees_raw = row[idx_attendees]
        industry = row[idx_industry] if idx_industry is not None else None

        # --- Duplicate Protection ---
        if idx_email_uuid is not None and row[idx_email_uuid].strip():
            skipped_count += 1
            continue

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

        # Step 3b: Generate email + MOM
        print("[GEMINI] Generating MOM and follow-up...")
        email_data = generate_email.generate(brand, attendees_raw, transcript, industry=industry)
        if not email_data:
            print("   [SKIP] Gemini could not generate content.")
            continue

        # Step 3c: Generate mockup image
        print(f"[IMAGE] Generating mockup for {brand}...")
        mockup = None
        if "image_prompt" in email_data:
            mockup = generate_image.create_mockup(brand, email_data["image_prompt"])
        else:
            print(f"   [WARNING] No image_prompt found in Gemini output for {brand}. Skipping image.")

        # Step 3d: Send email
        to_emails = send_email.parse_attendees(attendees_raw)
        if not to_emails:
            print("   [SKIP] No client email found.")
            continue

        # --- Test Mode Override ---
        meeting_title = row[idx_title] if idx_title is not None else brand
        
        # Handle new subject_options format (pick first one as default for automation)
        if "subject_options" in email_data and email_data["subject_options"]:
            subject = email_data["subject_options"][0]
        else:
            subject = email_data.get("subject", f"Follow up: {brand}")

        if TEST_MODE:
            to_emails = TEST_EMAIL if isinstance(TEST_EMAIL, list) else [TEST_EMAIL]
            subject = f"[TEST - Row {i} | {brand}] {subject}"
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
