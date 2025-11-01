import os

import datetime
import os.path
import time
import base64
import mimetypes
import traceback
from email.mime.text import MIMEText
from email.message import EmailMessage
import io # For GDrive downloads
import re
import markdown 
import json
import fitz
import requests
from typing import Iterable, List, Optional, Tuple
import html
import tiktoken

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from zoneinfo import ZoneInfo

from google import genai
import pandas as pd
from google.genai import types
from typing import Any, Dict, Optional
from openai import OpenAI
from openai import APIError, BadRequestError, RateLimitError
from dotenv import load_dotenv

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/documents'
]

creds = None
if os.path.exists("token.json"):
    creds = Credentials.from_authorized_user_file("token.json", SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        # Put your downloaded OAuth client file here
        flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        creds = flow.run_local_server(port=0)
    with open("token.json", "w") as f:
        f.write(creds.to_json())

# Build gmail service
gmail = build("gmail", "v1", credentials=creds)

# Build sheet service
sheets_service = build("sheets", "v4", credentials=creds)

# Build drive service
drive_service = build("drive", "v3", credentials=creds)

# Build docs service
docs_service = build('docs', 'v1', credentials=creds)

# Initialize tiktoken encoding to count number of tokens
enc = tiktoken.get_encoding("o200k_base")

# Write a function to create a doc file in a particular folder and return doc id
def create_google_doc_in_folder(drive_service, folder_id, doc_name, text, transcript_id):
    doc_id = None
    try:
        file_metadata = {
            'name': doc_name,
            'mimeType': 'application/vnd.google-apps.document',
            'parents': [folder_id]
        }
        created = drive_service.files().create(
            body=file_metadata,
            fields='id, name, parents'
        ).execute()
        
        print(f"Created Google Doc: {created['name']} (ID: {created['id']})")
        
        doc_id = created['id']
        requests = [
            {
                'insertText': {
                    'location': { 'index': 1 },
                    'text': text
                }
            }
        ]
    
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
        
        print(f"Written content in file: {created['name']} (ID: {created['id']})")
        
        drive_service.files().update(
            fileId=doc_id,
            body={
                'appProperties': {
                    'transcript_id': transcript_id
                }
            }
        ).execute()
        
        print(f"Tagged the file: {created['name']} with transcript id: {transcript_id}")
    
    except Exception as e:
        print(f"An error occured while creating google doc {e}")
    return doc_id

# Write a function to write content in a doc file with given doc id
def write_into_doc(docs_service, doc_id, text):
    requests = [
        {
            'insertText': {
                'location': { 'index': 1 },
                'text': text
            }
        }
    ]
    
    try:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={'requests': requests}
        ).execute()
    except:
        print("An error occured while writing into google doc")

# Write a function to update the transcript sheet and to update master sheet with doc link
def write_data_into_sheets(sheets_service, sheet_id, range, data):
    
    values = data

    body = {
        'values': values
    }
    try: 
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=range,
            valueInputOption='RAW',
            body=body
        ).execute()
        print(f"Updated values: {data} in sheet: {sheet_id}")
    except Exception as e:
        print(f"An error occured while writing {data} values in sheet: {sheet_id}: {e}")

def read_data_from_sheets(sheets_service, sheet_id, range):

    try:
        result = (
                sheets_service.spreadsheets()
                .values()
                .get(spreadsheetId=sheet_id, range=range)
                .execute()
            )
        sheet_data = result.get("values", [])
        print(f"{len(sheet_data)} rows retrieved")
        return sheet_data
    except HttpError as error:
        print(f"An error occurred: {error}")    

load_dotenv()

# Configuring Gemini model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBeyEkmnBeTAlHYhXpLotPyU1uG2zduDLw")
try:
    client = genai.Client(api_key = GEMINI_API_KEY)
    # Using a specific model version. 1.5 Flash is faster and cheaper for many tasks.
    # For higher quality, consider 'gemini-1.5-pro-latest'.
    print(f"Gemini model configured successfully.")
except Exception as e:
    print(f"Error configuring Gemini API: {e}")

# Configuring OpenAI client
client = OpenAI()

master_sheet_id = "1xtB1KUAXJ6IKMQab0Sb0NJfQppCKLkUERZ4PMZlNfOw"
brands_sheet_id = "1knG6IgrVf-Uw884jK2XuffZtiZEmVV30MkP59pHxU6M"

master_data = read_data_from_sheets(sheets_service, master_sheet_id, "Meeting_data!A:AK")
df_master = pd.DataFrame(master_data[1:], columns = master_data[0])

brand_data = read_data_from_sheets(sheets_service, brands_sheet_id, "Sheet7!A:P")
df_brand = pd.DataFrame(brand_data[1:], columns = brand_data[0])

mask = (df_master['Meeting Done'] == 'Conducted') & (df_master['Brand Size'].notna() & df_master['Brand Size'].astype("string").str.strip().ne(""))
df_master = df_master.loc[mask].copy()

prompt_template = """

# Role
You are Gautam Krishnamurthi, a Business Development Representative for NoBrokerHood (NBH), NoBroker’s gated-community “society management” platform used by resident communities. NBH combines visitor/security management with resident apps, an admin dashboard for committees, and modules for billing, accounting, complaints, amenities, notices, classifieds/marketplace, and more. Your task is to pitch NBH advertising solutions through personalized emails to brands and close deals.

You will receive:
- Brand name in <BRAND>…</BRAND>
- Brand POC email in <EMAIL>…</EMAIL>
- Brand POC name in <POC_NAME>…</POC_NAME>
- Proposed industry in <INDUSTRY>…</INDUSTRY>
- Prior meetings (same industry) in <PREVIOUS_MEETINGS>…</PREVIOUS_MEETINGS>
- Case studies (same industry) in <CASE_STUDIES>…</CASE_STUDIES>
- A festival-season asset menu in <ASSETS_TO_BE_PTCHED_FOR_FESTIVE_SEASON>…</ASSETS_TO_BE_PTCHED_FOR_FESTIVE_SEASON>
- A jargon glossary in <JARGON_GLOSSARY>…</JARGON_GLOSSARY>

# Goal
Write a **short, personalized human-sounding festive-season cold email** to <BRAND> that feels like it was typed by a person (not a marketing flyer). Keep it concise and actionable.

# Allowed Industries
[
  "FMCG","Automotive & Transportation","Membership & Local Services","Marketing, Advertising & Media","Apparel & Fashion","Food & Beverage","Healthcare","Finance & Fintech","Beauty & Personal Care","Jewellery","Real Estate & Construction","Energy, Renewables & Mining","Wellness & Fitness","Education & Training","Home Goods & Electronics","Hospitality & Travel","Technology & Business Services","E-Commerce","Retail","Pets & Pet Services","Gaming","Logistics & Warehousing","Other / Unknown","Manufacturing & Industrial","Quick Commerce","Pharma","OTT"
]

# Industry Matching
1) Map <BRAND> to an industry from the Allowed list if you are **highly confident**.
2) If your confident classification **differs** from <INDUSTRY>, output only:
   {{"new_industry":"<your_industry_from_allowed_list>"}}
3) If you are **not confident** or it’s ambiguous, **do not override**; proceed using the provided <INDUSTRY>.

# Methodology
- Read <PREVIOUS_MEETINGS> and <CASE_STUDIES> to understand **this industry’s needs**, which **NBH placements** fit best, and any **ROI/outcomes** mentioned.
- Choose relevant **festival-season assets** from <ASSETS_TO_BE_PTCHED_FOR_FESTIVE_SEASON> that align to the brand and the industry needs.
- **Name-drops:** Use brand names that NBH has worked with in the subject and email body. Only mention brands explicitly present in <PREVIOUS_MEETINGS> or <CASE_STUDIES>. If none fit, skip name-drops. Do not include brand which belongs to the same parent company as <BRAND>
- **Glossary & phrasing:** Translate NBH internal terms with <JARGON_GLOSSARY>.
- Use these friendly phrases where relevant (you can also think of similar phrases, no need to stick to these):
  - **Digital Takeover** → Digital placements (e.g., In-App Full-Screen Video Ads, In-App Discovery Banners, Digital Notice Board, Post-Approval Screen Lead Forms)
  - **On-ground magic** → On-ground activations/BTL (e.g., Elevator/Gate Branding, Festive Hamper Inserts & Sampling, society events)
- Create a compelling subject line related to the {{industry}} that includes the brand name-drops like (do not use [], {{}}, or () in subject):
  - "[Brand1] and [Brand2] tapped NoBrokerHood kitchens - {{your_brand}} wasn't on the menu" - for "Food & Beverage"
  - "[Brand1] and [Brand2] plugged into NoBrokerHood - {{your_brand}} missed the switch" - for "Home Goods & Electronics"
  - etc.
- Create gentle urgency (FOMO) by mentioning other relevant brands email body **without saying “competitor”**. If you reference other brands, use names only when provided.
- Include a short crisp overview of NoBrokerHood in the begnning telling that NoBrokerHood connects brands directly with residents inside thousands of gated communities across India—a high-intent audience that engages actively with digital and on-ground campaigns."
- Include this link of pitch deck in the email with the HTML tags: <a href="https://www.canva.com/design/DAGfKxefahY/sg1k0ES4y3phNe_vE35hrQ/view?utm_content=DAGfKxefahY&utm_campaign=designshare&utm_medium=link2&utm_source=uniquelinks&utlId=h3fc1bc71be#1"> NoBrokerHood Brand Partnerships </a>
- Start the email with "Hi <POC_NAME>," if <POC_NAME> is a single name. If multiple names are present, use "Hi <POC_NAME1> and team,". Use POC_NAME only if it looks like a personal name (not a role or generic term). Otherwise start with "Hi there,".
- **Personalize**: Use web search to understand <BRAND> profile and products. Using this information (if you are confident) personalize the email for <BRAND> using 1 sentences specific to brand. Skip this part if you can't find this information.
- Do not include any signature or sign-off in the email.

# Style & Formatting (Plain Text Only)
- **Plain text email**, no HTML except for the one link above.
- The only formatting allowed is **bold emphasis** using `**...**` for short phrases and headings/titles.
- Keep it natural: 2–3 brief paragraphs, optionally 1 tight bullet list (max 3 bullets).
- Tone: crisp, helpful, outcomes-oriented; no hype; no emojis.
- Include a single clear next step (e.g., share festive slots, 15-min chat, preferred societies).

# Output Shape
If the industry override triggers, output a pure JSON object:
{{"new_industry":"<one_from_Allowed_or_'Other / Unknown'>"}}

If the industry match succeeds, output a pure JSON object with exactly:
{{
  "subject": "<string>",
  "email_content": "<plain-text body with optional **bold** phrases only>"
}}

# Content Rules & Safety Rails
- **No hallucinations.** Do not invent brand names, ROI, placements, or timelines absent from inputs.
- **Name-drops:** Only if present in <PREVIOUS_MEETINGS>/<CASE_STUDIES>. Never use the word “competitor”. Do not use brands belonging to the same parent company as <BRAND> e.g. Hotstar and JioHotstar
- **ROI/Proof:** Mention only if present in inputs; keep it concise.
- **Keep it short.** Target 90–150 words for the body.

# Final Output Constraints (Strict Rules)
- Output must be a **pure JSON object** (no code fences, no extra commentary).
- JSON must be syntactically valid (no trailing commas).
- If industry override is triggered, output only {{"new_industry":"..."}} and nothing else.
- **DO NOT INCLUDE WEB SEARCH CITATIONS IN YOUR OUTPUT**.
- Do not express doubt. Be confident and clear. Do not use weak sounding phrases like "I noticed", "I see", "I saw" etc.

----
<BRAND>
  {brand_name}
</BRAND>

<INDUSTRY>
  {industry}
</INDUSTRY>

<PREVIOUS_MEETINGS>
  {previous_meetings}
</PREVIOUS_MEETINGS>

<CASE_STUDIES>
  {case_studies}
</CASE_STUDIES>

<ASSETS_TO_BE_PTCHED_FOR_FESTIVE_SEASON>
  {{
    "Home Goods & Electronics": [
      "Targeted Move-in / Move-out Cohort Outreach via PAC",
      "Festival-focused Video Pop-up Ads with festival offers or discounts",
      "Lift Branding + Festive Gift Bag Leaflet Inserts"
    ],
    "Education & Training": [
      "Sponsored cultural or festival celebration events in gated communities",
      "PAC lead gen campaigns for seasonal courses, workshops",
      "Festive Digital Notice Board push campaigns with early bird offers"
    ],
    "Manufacturing & Industrial": [
      "Festival-themed sponsored educational content in forums",
      "Targeted Move-in / Move-out Cohort Outreach via PAC",
      "Lead capture video pop-ups with festival logistics planning or safety tips"
    ],
    "Automotive & Transportation": [
      "Test Drive Festive Offers Campaign via PAC + Video Pop-ups",
      "Location-Targeted Ads near competitor locations",
      "Geo-fenced Lift Branding + Gift Bag Leaflets in Premium Societies"
    ],
    "Marketing, Advertising & Media": [
      "Festival-targeted digital campaigns (PAC + Video + DNB)",
      "Exclusive Lift & Gate Branding with festive theming",
      "Sponsor festive events and competitions within gated societies"
    ],
    "Hospitality & Travel": [
      "Festive booking promos via targeted PAC + DNB pushes",
      "Behavioral Cohort Targeting + PAC for Festival Stays/Bookings",
      "Gift Bag Leaflets in Premium Societies"
    ],
    "Apparel & Fashion": [
      "Festive digital product launches via Video Pop-up + Discover + PAC",
      "Lift Branding + coupon Inserts in Festival Gift Bags",
      "Sponsor cultural festivals for social storytelling"
    ],
    "Jewellery": [
      "Festival-exclusive lift branding + coupon dispensers",
      "Video Pop-ups with festive-themed collection reveals",
      "Participate/sponsor society festive events"
    ],
    "Retail": [
      "Proximity-targeted Festival Season PAC + Discover + DNB Campaigns",
      "Lift Branding + Leaflet Inserts in Gift Bags + Door Hanger Flyers",
      "Pre-festival Sampling and Flea Market Stalls"
    ],
    "Healthcare & Wellness & Fitness": [
      "Festival wellness camps & health check booths",
      "Push campaigns on health supplements/product discounts",
      "PAC + Video Pop-ups for diet/fitness coaching"
    ],
    "Food & Beverage / FMCG": [
      "Opt-in & Door-to-door Sampling + Festive Gift Bag Inserts",
      "Burst Video Pop-up + PAC campaigns during festive days",
      "Sponsor cultural festivals and community kitchens"
    ],
    "Technology & Business Services": [
      "Lead gen PAC + Festival event RSVP engagement",
      "DNB push campaigns with festive greetings + product bundles",
      "Sponsored gated community discussions/content"
    ],
    "Startups / Price-sensitive": [
      "Festival promo Discovery + PAC + light DNB burst",
      "Gift bag leaflet sponsorship with samples",
      "Sponsor selected festival nights with low-cost sampling"
    ],
    "Beauty & Personal Care": [
      "Festival-time opt-in product sampling + PAC + coupons",
      "Video Pop-ups highlighting festive gift collections",
      "Sponsor Diwali/Garba experiential booths"
    ],
    "E-Commerce": [
      "Festival flash sale promos via PAC + DNB",
      "Curated festive Discover carousels for gifting bundles",
      "Sampling/leaflet distribution in gift bags"
    ],
    "Real Estate & Construction": [
      "Mover/renovator targeting using move-in/move-out cohorts",
      "Sponsored festival celebrations for brand goodwill",
      "Geo-fenced video tours and Discover banners with festive discounts"
    ],
    "Finance & Fintech": [
      "Festive loan/insurance offers via PAC and Video Pop-ups",
      "Sponsored festival events + festive-themed content",
      "DNB push campaigns with reminders"
    ],
    "Pets & Pet Services": [
      "Festive pet treat sampling in gated societies",
      "PAC + Video Pop-up on pet care promotions",
      "Sponsor community pet events"
    ],
    "Membership & Local Services": [
      "Festive sign-up drives via PAC and DNB",
      "On-ground festival event sponsorships",
      "Discover banners with seasonal packages"
    ],
    "Energy, Renewables & Mining": [
      "Awareness & subsidy pushes via PAC and video pop-ups",
      "Energy-safety festivals/community events",
      "Geo-fenced Discover banners for eco-friendly offers"
    ],
    "Entertainment & Gaming": [
      "Limited-time bundles via PAC + video pop-ups",
      "Sponsored community festivals and competitions",
      "DNB push with curated entertainment content"
    ],
    "Logistics & Warehousing": [
      "Express delivery promos via PAC and DNB",
      "Festive-themed sampling (box inserts)",
      "Driver recognition/community goodwill festivals"
    ],
    "Quick Commerce": [
      "Flash sale bursts using Video Pop-up and PAC",
      "Sampling festive snack gift packs",
      "DNB offer countdowns and reminders"
    ],
    "Education": [
      "Festival cultural event sponsorships",
      "PAC-based course registrations with festive discounts",
      "DNB class/event reminders aligned to breaks"
    ],
    "Furniture": [
      "On-ground festival showcases & sampling",
      "PAC + Video Pop-up for festive discounts",
      "Leaflet inclusion in festive gift bags"
    ],
    "Automotive": [
      "Festival test drive & launch events with video and PAC",
      "Digital geo-fencing bursts",
      "Festival sponsorship of cultural events"
    ],
    "Beauty": [
      "Opt-in sampling + festive PAC and coupons",
      "Video Pop-ups showcasing gift sets",
      "Sponsor Diwali/Garba experiential booths"
    ],
    "Robotics": [
      "Product demos paired with PAC lead gen",
      "Sponsored tech showcases",
      "DNB push with festive offers"
    ],
    "Accounting Services": [
      "Festival tax-planning offers via PAC and DNB",
      "Community financial literacy events",
      "Video Pop-ups for appointment scheduling"
    ],
    "Kitchenware": [
      "Gifting bundle promos via Discover & PAC",
      "Sampling in festive gift bags",
      "On-ground experiential activations"
    ],
    "Culinary Arts": [
      "Festival cooking contests collaboration",
      "Post-Approval Coupons for recipe kits",
      "Sampling during festivals"
    ],
    "Entertainment": [
      "Festive offers & event promos via PAC, Video Pop-up, DNB",
      "Sponsor movie nights",
      "Discover banners with seasonal content"
    ],
    "Water Treatment Services": [
      "Health-benefit awareness via PAC + Video pop-ups",
      "Community water quality events",
      "Leaflet sampling in gift bags"
    ],
    "Food and Beverage Services": [
      "Seasonal sampling + opt-in engagement",
      "PAC + DNB for festive menu offers",
      "Sponsor cultural food fests"
    ],
    "Fashion": [
      "Digital launches: Video Pop-ups + PAC + Discover",
      "Sampling + festive gift bag inserts",
      "Sponsor cultural events (Garba, Navratri)"
    ],
    "Media Agency": [
      "Festival campaign bundles (digital + BTL)",
      "Lift & Gate festive takeovers + experiential",
      "Event sponsorships and contests"
    ],
    "Car Detailing": [
      "Festive-package promos via PAC + DNB",
      "Sampling/gift packs in gift bags",
      "Sponsor society meet-ups and demos"
    ],
    "Advertising Agencies": [
      "Multi-client festival packages",
      "Sponsored cultural events",
      "Exclusive ad inventory reservation"
    ],
    "Home Services": [
      "Festive discounts via PAC + Video ads",
      "Sampling/leaflet inclusion in gift bags",
      "Sponsor local society demos"
    ],
    "Food Delivery": [
      "Flash sales via Video Pop-up + PAC",
      "Sampling partner promos at food festivals",
      "Sponsor cultural food celebrations"
    ],
    "Advertising": [
      "Festival-themed awareness & conversion",
      "Lift and gate branding campaigns",
      "Sponsor community cultural events"
    ],
    "Facility Management": [
      "Festive rate promos via DNB and PAC",
      "On-ground cleaning product demos",
      "Community safety workshops"
    ]
  }}
</ASSETS_TO_BE_PTCHED_FOR_FESTIVE_SEASON>

<EMAIL>
  {email}
</EMAIL>

<POC_NAME>
  {poc_name}
</POC_NAME>

<JARGON_GLOSSARY>
  {{
    "PAC":"Post-Approval Screen Coupons / Lead Forms",
    "PAC lead gen campaigns":"Post-Approval Screen Lead-Gen Campaigns",
    "Post-approval card coupons":"Post-Approval Coupons",
    "DNB":"Digital Notice Board (in-app announcements)",
    "DNB push":"In-App Announcement Push Campaigns",
    "Discover":"In-App Discovery Feed (carousel placements)",
    "Discover carousels":"In-App Discovery Feed (carousel placements)",
    "Discover banners":"In-App Discovery Banners",
    "Video Pop-ups":"In-App Full-Screen Video Ads",
    "Lift Branding":"Elevator Panel Branding",
    "Gate Branding":"Society Gate Branding",
    "Gift Bag Leaflet Inserts":"Festive Gift Hamper Inserts (leaflets/samples)",
    "Door-to-door hangers":"Door Hanger Flyers",
    "Geo-fenced":"Location-Targeted (Geo-fenced) Ads",
    "Proximity Targeted":"Location-Targeted Ads",
    "Behavioral Cohort Targeting":"Audience Targeting by Behavior/Cohorts",
    "Move-in / Move-out Cohort Outreach":"New-Mover / Move-Out Audience Targeting",
    "RSVP engagement":"In-App Event RSVP Collection",
    "BTL":"On-Ground Activations",
    "Inventory locks":"Exclusive Ad Inventory Reservation",
    "Digital burst":"Short High-Frequency Flight",

    "Digital Takeover":"Digital placements (Video Pop-ups, Discover Banners, DNB pushes, PAC lead forms)",
    "On-ground magic":"On-ground activations (Elevator/Gate Branding, Festive Hamper Inserts & Sampling, society events)"
  }}
</JARGON_GLOSSARY>
"""

def get_gemini_response_json(brand_name, industry, previous_meetings, email, poc_name, case_studies):
    """Sends transcript text to Google Gemini API and retrieves raw insights text."""

    prompt_json = prompt_template.format(
    brand_name = brand_name, industry = industry, previous_meetings = previous_meetings, email=email, case_studies=case_studies, poc_name=poc_name)
    
    grounding_tool = types.Tool(
        google_search=types.GoogleSearch()
    )

    # Configure generation settings
    config = types.GenerateContentConfig(
        tools=[grounding_tool]
    )
    
    try:
        response = client.models.generate_content(model="gemini-2.5-flash",contents=prompt_json, config=config)
        raw_text = response.candidates[0].content.parts[0].text
        cleaned_json_str = re.sub(r'```json\s*|\s*```', '', raw_text).strip()
        return cleaned_json_str
    
    except genai.exceptions.GoogleGenAIError as e:
        print(f"Google GenAI error: {e}")
        return None
    
# Functions to generate email using OpenAI GPT
def _to_jsonable(obj: Any) -> Any:
    """
    Best-effort conversion of common Python objects (e.g., pandas DataFrame)
    into JSON-serializable structures.
    """
    # pandas DataFrame/Series support (duck-typed)
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict(orient="records")  # DataFrame
        except TypeError:
            return obj.to_dict()  # Series / generic mapping
    # Already JSON-serializable primitives/containers
    if isinstance(obj, (dict, list, str, int, float, bool)) or obj is None:
        return obj
    # Fallback: string-coerce
    return str(obj)

def get_gpt_response_json(
    brand_name: str,
    industry: str,
    previous_meetings: Any,
    email: str,
    case_studies: Any,
    model: str = "gpt-4.1-mini",
    use_web_search: bool = True,
    poc_name: str = "there",
) -> Optional[str]:

    # Render the prompt with your variables
    prompt_json = prompt_template.format(
        brand_name=brand_name,
        industry=industry,
        previous_meetings=previous_meetings,
        email=email,
        case_studies=case_studies,
        poc_name=poc_name
    )

    # Build tool list (web grounding)
    tools = [{"type": "web_search"}] if use_web_search else None
    input_tokens = len(enc.encode(prompt_json))
    try:
        # Ask the model for STRICT JSON (no code fences, no chatter)
        resp = client.responses.create(
            model=model,
            input=prompt_json,
            tools=tools  # or use a json_schema if you want a stricter contrac
        )

        # Preferred: resp.output_text contains the JSON when using response_format
        raw_text = getattr(resp, "output_text", None)
        if not raw_text:
            # Fallback path (should rarely be needed)
            # Try to reconstruct from content parts if output_text is unavailable
            try:
                parts = resp.output[0].content[0].text  # SDK structure fallback
                raw_text = parts
            except Exception:
                raw_text = ""

        # Clean up accidental fences if any (shouldn’t appear with response_format)
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_text.strip(), flags=re.IGNORECASE)

        # Ensure it’s valid JSON; if so, re-dump to canonical string
        try:
            parsed: Dict[str, Any] = json.loads(cleaned)
            return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            # Last-ditch: extract first {...} or [...] chunk
            m = re.search(r"(\{.*\}|\[.*\])", cleaned, flags=re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group(1))
                    return json.dumps(parsed, ensure_ascii=False)
                except Exception:
                    pass
            # Return whatever we got so caller can log/debug
            return cleaned or None

    except (BadRequestError, RateLimitError, APIError) as e:
        print(f"OpenAI API error: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error: {e}")
        return None


def text_to_minimal_html(text: str) -> str:
    ALLOWED_SCHEMES = ("http://", "https://", "mailto:")
    A_RE = re.compile(
        r'<a\s+href=[\'"](https?://[^\'"]+|mailto:[^\'"]+)[\'"][^>]*>(.*?)</a>',
        re.I | re.S
    )

    # 0) Tokenize and sanitize <a> tags so they survive escaping
    anchors = []
    def _a_repl(m):
        url = m.group(1).strip()
        label = (m.group(2) or url).strip()
        if not url.lower().startswith(ALLOWED_SCHEMES):
            return html.escape(m.group(0))  # unsafe -> escape whole thing
        safe = f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
        tok = f"@@A{len(anchors)}@@"
        anchors.append(safe)
        return tok
    tokenized = A_RE.sub(_a_repl, text)

    # 1) Escape everything else
    esc = html.escape(tokenized)

    # 2) **bold** -> <strong>...</strong>
    esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)

    # 3) Linkify bare URLs (not inside tokens)
    esc = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', esc)

    # 4) Paragraphs + "- " bullets -> <ul><li>…</li></ul>
    lines = esc.splitlines()
    parts, i = [], 0
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*-\s+", line):
            parts.append("<ul>")
            while i < len(lines) and re.match(r"^\s*-\s+", lines[i]):
                item = re.sub(r"^\s*-\s+", "", lines[i]).strip()
                parts.append(f"<li>{item}</li>")
                i += 1
            parts.append("</ul>")
            continue
        parts.append("" if not line.strip() else f"<p>{line}</p>")
        i += 1
    esc = "\n".join(parts)

    # 5) Restore sanitized anchors
    for idx, a in enumerate(anchors):
        esc = esc.replace(f"@@A{idx}@@", a)

    return f"<!doctype html><meta charset='utf-8'>\n<div>{esc}</div>"



def send_email(
    service,
    to: Iterable[str] | str,
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    sig_gif_path = "unnamed.gif",
    sig_name="Gautam Krishnamurthi",
    sig_title="Brand Partnerships & Alliances",
    sig_phone="+91 7676890529",
    sig_org="NoBrokerHood",
    attachments: Optional[List[str]] = None,
    cc: Optional[Iterable[str] | str] = None,
    bcc: Optional[Iterable[str] | str] = None,
    reply_to: Optional[str] = None,
) -> dict:
    
    sig_cid = "siggif"  # the content-id token you’ll reference in <img src="cid:siggif">
    sig_html = f"""
    <hr>
    <p><img src="cid:{sig_cid}" alt="{html.escape(sig_org)}" width="72"></p>
    <p><strong>{html.escape(sig_name)}</strong><br>
    {html.escape(sig_title)}<br>
    <a href="tel:{html.escape(sig_phone)}">{html.escape(sig_phone)}</a> | {html.escape(sig_org)}</p>
    """
    full_html = f"{body_html}\n{sig_html}"
    full_text = f"""{body_text}

    --
{sig_name}
{sig_title}
{sig_phone} | {sig_org}
"""
    msg = EmailMessage()
    msg["Subject"] = subject

    def _join(value):
        if value is None:
            return None
        return value if isinstance(value, str) else ", ".join(value)

    msg["To"] = _join(to)
    if cc: msg["Cc"] = _join(cc)
    if bcc: msg["Bcc"] = _join(bcc)
    if reply_to: msg["Reply-To"] = reply_to

    # Add body (plain + optional HTML)
    msg.set_content(full_text)
    if body_html:
        msg.add_alternative(full_html, subtype="html")
    html_part = msg.get_body(preferencelist=("html",))
    with open(sig_gif_path, "rb") as f:
        html_part.add_related(
            f.read(),
            maintype="image",
            subtype="gif",     # or detect via mimetypes if you prefer
            cid=sig_cid,        # referenced by src="cid:siggif"
            filename = "NoBrokerHood Brand Partnerships"
        )

    # Add attachments
    for path in attachments or []:
        path = os.path.expanduser(path)
        filename = os.path.basename(path)
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype,
                filename=filename,
            )

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()

def main():
    
    with open("case_studies.json", "r", encoding="utf-8") as f:
      case_studies = json.load(f)

    relevant_columns = ['Brand Name', 'Key Discussion Points', 'Key Questions', 'Action items', 'Marketing Assets', 'Customer Needs', 'Positive Factors', 'Closure Score', 'Pitch Rating', 'Client Pain Points', 'Overall Client Sentiment']
    final_output = []
    api_count = 0
    sent_mail_count = 0
    for i, row in df_brand[:10000].iterrows():
        case_studies_selected = []
        if row['Touched in last 3 months based on email domain'] == 'True':
            continue
        brand_name = row['Company / Brand Name']
        industry = row['top1_industry']
        if industry == 'Other / Unknown':
            industry = row['top2_industry']
        df_pm = df_master.loc[(df_master['Industry'] == industry)].copy()
        previous_meeting_intelligence = []
        for j, row2 in df_pm.iterrows():
            meeting_intelligence = {col: row2[col] for col in relevant_columns}
            previous_meeting_intelligence.append(meeting_intelligence)
        for c in case_studies:
            if c["Industry"] == industry:
                case_studies_selected.append(c)
        
        name = row["Client POC Name"]
        email = row['Email'].strip().split(',')
        result = get_gpt_response_json(brand_name, industry, previous_meeting_intelligence, email, case_studies_selected, "gpt-5-mini", True, poc_name=name)
        out_token = len(enc.encode(result))

        sheet_index = i+2

        
        try:
            email_subject = json.loads(result).get("subject", "")
            email_content = json.loads(result).get("email_content", "")
            email_content_html = text_to_minimal_html(email_content) if email_content else None
            if not email_subject or not email_content_html:
                print(f"Skipping email for {brand_name} due to missing subject or content.")
                data = [["", f"{out_token}", f"{result}"]]
                rng = f"Sheet7!T{sheet_index}:V{sheet_index}"
                write_data_into_sheets(sheets_service, brands_sheet_id, rng, data)
                continue
            resp = send_email(gmail,email, email_subject, email_content, body_html = email_content_html,cc='brand.vmeet@nobroker.in' ,bcc='mrityunjay.pandey@nobroker.in')
            api_count += 1
            if (api_count % 20) == 0:
                print("Sleeping for 60 seconds to respect rate limits...")
                time.sleep(60)
            sent_id = resp.get("id")
            if not sent_id:
              data = [["False", "Email not sent", "", "", "", out_token]]
              rng = f"Sheet7!P{sheet_index}:U{sheet_index}"
              write_data_into_sheets(sheets_service, brands_sheet_id, rng, data)
            else:
                data = [["True", sent_id, "", "", "", out_token]]
                rng = f"Sheet7!P{sheet_index}:U{sheet_index}"
                write_data_into_sheets(sheets_service, brands_sheet_id, rng, data) 
                sent_mail_count += 1
                if sent_mail_count == 620:
                    break    
        except Exception as e:
            print(f"Error sending email: {e}")
            data = [["True", "Email not sent", "", "", "" ,out_token,f"Error while sending email {e}"]]
            rng = f"Sheet7!P{sheet_index}:V{sheet_index}"
            write_data_into_sheets(sheets_service, brands_sheet_id, rng, data)


if __name__ == "__main__":
    main()


