
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

BASE_DIR = r'c:\Users\bharg\OneDrive\Desktop\Bhargav Kulkarni 44\3in1 Agent\outbound_automation'
TOKEN_PATH = os.path.join(BASE_DIR, 'token.json')
creds = Credentials.from_authorized_user_file(TOKEN_PATH)
service = build('sheets', 'v4', credentials=creds)
spreadsheet_id = '1Cx32uP3yiNa2tBQ1aBPHmBcd9jnkK88B01Kg3LnOI7I'

# result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range='Meeting_data!A:AZ').execute()
result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range='Meeting_data!A:CF').execute()
values = result.get('values', [])
headers = [h.strip() for h in values[0]]
print(f"Headers found: {len(headers)}")

def find_idx(name):
    for i, h in enumerate(headers):
        if name.lower() in h.lower():
            return i
    return None

i_dur = find_idx('Meeting duration')
i_done = find_idx('Meeting Done')
i_cls = find_idx('Closure Status')

if i_dur is None or i_done is None or i_cls is None:
    print(f"Indices: Dur:{i_dur}, Done:{i_done}, Cls:{i_cls}")
    print("Full headers:", headers)
    exit()


count_5_plus = 0
count_10_plus = 0
total_conducted_not_closed = 0

for row in values[1:]:
    while len(row) <= max(i_dur, i_done, i_cls):
        row.append('')
    
    done = row[i_done].strip().lower()
    closure = row[i_cls].strip().lower()
    
    if done == 'conducted' and closure != 'close':
        total_conducted_not_closed += 1
        try:
            dur = float(row[i_dur].strip() or 0)
        except:
            dur = 0
            
        if dur >= 5:
            count_5_plus += 1
        if dur >= 10:
            count_10_plus += 1

print(f"Total Conducted & Not Closed Leads: {total_conducted_not_closed}")
print(f"Leads with Duration >= 5 mins: {count_5_plus}")
print(f"Leads with Duration >= 10 mins: {count_10_plus}")

