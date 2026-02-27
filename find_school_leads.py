
import config
import google_auth
import json

def find_schools():
    services = google_auth.get_services()
    result = services['sheets'].spreadsheets().values().get(
        spreadsheetId=config.SPREADSHEET_ID, 
        range=config.MEETING_DATA_SHEET + '!A1:Z500'
    ).execute()
    
    rows = result.get('values', [])
    if not rows:
        print("No rows found")
        return
        
    headers = rows[0]
    
    # Try to find standard columns
    brand_idx = -1
    transcript_idx = -1
    
    for i, h in enumerate(headers):
        if "brand" in h.lower(): brand_idx = i
        if "transcript" in h.lower(): transcript_idx = i
        
    leads = []
    for i, row in enumerate(rows[1:], start=2):
        brand_name = row[brand_idx] if brand_idx != -1 and len(row) > brand_idx else ""
        if "school" in brand_name.lower() or "education" in brand_name.lower() or "academy" in brand_name.lower():
            transcript_url = row[transcript_idx] if transcript_idx != -1 and len(row) > transcript_idx else ""
            leads.append({"brand": brand_name, "transcript": transcript_url, "row": i})
            
    print(json.dumps(leads[:5], indent=2))

if __name__ == "__main__":
    find_schools()
