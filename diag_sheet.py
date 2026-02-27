
import config
import google_auth

def diag():
    services = google_auth.get_services()
    print(f"[SHEET] Reading {config.MEETING_DATA_SHEET}...")
    result = services["sheets"].spreadsheets().values().get(
        spreadsheetId=config.SPREADSHEET_ID,
        range=f"{config.MEETING_DATA_SHEET}!A1:CF20"
    ).execute()

    rows = result.get("values", [])
    if not rows:
        print("No data found.")
        return

    headers = [h.strip() for h in rows[0]]
    
    def find_col(k):
        for i, h in enumerate(headers):
            if k.lower() in h.lower(): return i
        return None

    idx_brand = find_col("Brand Name")
    idx_dur = find_col("Meeting duration")
    idx_done = find_col("Meeting Done")
    idx_cls = find_col("Closure Status")
    idx_email_uuid = find_col("Email UUID")

    print(f"\nScanning first 20 rows...")
    for i, row in enumerate(rows[1:], start=2):
        while len(row) < len(headers): row.append("")
        brand = row[idx_brand] if idx_brand is not None else "Unknown"
        done = row[idx_done].lower().strip() if idx_done is not None else ""
        closure = row[idx_cls].lower().strip() if idx_cls is not None else ""
        uuid = row[idx_email_uuid].strip() if idx_email_uuid is not None else ""
        try:
            dur = float(row[idx_dur]) if idx_dur is not None else 0
        except:
            dur = 0
            
        is_conducted = (done == "conducted")
        is_not_closed = ("close" not in closure)
        is_long_enough = (dur >= config.MIN_MEETING_DURATION)
        is_new = (not uuid)

        status = "PASSED" if (is_conducted and is_not_closed and is_long_enough and is_new) else "FAILED"
        
        print(f"Row {i} [{brand}]: {status}")
        if status == "FAILED":
            reasons = []
            if not is_conducted: reasons.append(f"Not Conducted (is '{done}')")
            if not is_not_closed: reasons.append(f"Is Closed (is '{closure}')")
            if not is_long_enough: reasons.append(f"Too short ({dur} mins < {config.MIN_MEETING_DURATION})")
            if not is_new: reasons.append("Already processed (UUID exists)")
            print(f"   -> Reasons: {', '.join(reasons)}")

if __name__ == "__main__":
    diag()
