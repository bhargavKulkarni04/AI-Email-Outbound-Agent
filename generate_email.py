
"""
Generate Email Module
Uses Gemini 2.5 Flash to create Follow-up email based on real meeting transcript.
"""

import re
import json
import time
from google import genai
from google.genai import types
import config

client = genai.Client(api_key=config.GEMINI_API_KEY)

# --- Jargon Glossary ---
JARGON_GLOSSARY = {
    "PAC": "Post-Approval Screen Coupons / Lead Forms",
    "PAC lead gen campaigns": "Post-Approval Screen Lead-Gen Campaigns",
    "Post-approval card coupons": "Post-Approval Coupons",
    "DNB": "Digital Notice Board (in-app announcements)",
    "DNB push": "In-App Announcement Push Campaigns",
    "Discover": "In-App Discovery Feed (carousel placements)",
    "Discover carousels": "In-App Discovery Feed (carousel placements)",
    "Discover banners": "In-App Discovery Banners",
    "Video Pop-ups": "In-App Full-Screen Video Ads",
    "Lift Branding": "Elevator Panel Branding",
    "Gate Branding": "Society Gate Branding",
    "Gift Bag Leaflet Inserts": "Gift Hamper Inserts (leaflets/samples)",
    "Door-to-door hangers": "Door Hanger Flyers",
    "Geo-fenced": "Location-Targeted (Geo-fenced) Ads",
    "Proximity Targeted": "Location-Targeted Ads",
    "Behavioral Cohort Targeting": "Audience Targeting by Behavior/Cohorts",
    "Move-in / Move-out Cohort Outreach": "New-Mover / Move-Out Audience Targeting",
    "RSVP engagement": "In-App Event RSVP Collection",
    "BTL": "On-Ground Activations",
    "Inventory locks": "Exclusive Ad Inventory Reservation",
    "Digital burst": "Short High-Frequency Flight",
    "Digital Takeover": "Digital placements (Video Pop-ups, Discover Banners, DNB pushes, PAC lead forms)",
    "On-ground magic": "On-ground activations (Elevator/Gate Branding, Hamper Inserts & Sampling, society events)"
}

PROMPT_TEMPLATE = """
# Role
You are Bhargav Kulkarni, Brand Partnerships & Alliances at NoBrokerHood (NBH).
You have conducted a meeting and are writing a strategic follow-up email to {full_client_name}.

# STAGE 1: ANALYSIS
Study the <TRANSCRIPT> and identify 3 key strategic alignments or pain points discussed.

# STAGE 2: THE EMAIL (STRICT STRUCTURE)
Write the email EXACTLY following this structure and wording for the intro:

Hi {full_client_name},

NoBrokerHood connects brands directly with residents inside thousands of gated communities across India—a high-intent audience that engages actively with digital and on-ground campaigns. Given {brand_name}'s focus on innovative reach and driving consumer engagement, I thought our platform might be particularly interesting.

- [Strategic Point 1 from transcript]
- [Strategic Point 2 from transcript]
- [Strategic Point 3 from transcript]

I wanted to show how {brand_name} would look in our premium societies.

[Short professional CTA (e.g., Let me know when we can connect to discuss this further)]

STRICT RULES:
- NO signature at the end (No "Regards", "Sincerely", or "Best").
- NO names at the end. The email MUST end right after the CTA.
- DO NOT describe the assets (gate/lift) in the body text.
- Use a simple "-" dash for bullets.

# IMAGE PROMPT RULES (3-IN-1 VERTICAL COMPOSITE)
Create a highly realistic vertical collage image split into THREE distinct horizontal sections stacked top to bottom.
Each section must look like a candid smartphone photo taken inside a standard Indian residential society — NOT ultra-luxury, NOT studio lighting. Use natural, slightly overcast daylight.

- TOP SECTION — GATE BRANDING
  - A standard Indian apartment complex entrance. Black wrought-iron sliding gate.
  - A thin, flat 4ft x 3ft horizontal ACP board displaying a '{brand_name}' ad, mounted on the gate bars. FLAT board, NOT a thick lightbox.
  - Trees and apartment buildings visible naturally in the background.
  - A watchman at the gatehouse casually checking a logbook. A resident walking past in the background, not looking at the ad.

- MIDDLE SECTION — LIFT BRANDING
  - Brushed stainless steel elevator interior with vertical metallic grain texture.
  - An A3 size printed poster in a thin clean white acrylic frame showing the '{brand_name}' ad, mounted on the wall.
  - Elevator buttons and CCTV camera in corner visible.
  - A resident entering the lift holding a grocery bag, a maintenance worker visible in hallway behind — both going about their day.

- BOTTOM SECTION — DIGITAL IN-APP (PAC)
  - A clean, high-fidelity digital UI mockup (screenshot) of the NoBrokerHood mobile app on a smartphone screen.
  - TOP OF SCREEN: Clean iOS/Android style status bar (time, battery, signal).
  - APP HEADER: White header with "Back" button icon and title "My Visitors".
  - THE PAC OVERLAY: A large, crisp white card with rounded corners overlaying the screen.
      - Includes a green circular icon with a white checkmark.
      - Bold black text: "Pre approval created".
      - Small grey text: "for your {brand_name} delivery".
  - THE AD CREATIVE: Below the notification card, a large, high-resolution square advertisement for '{brand_name}' with sharp branding and professional graphics.
  - BACKGROUND OF UI: The apartment list behind the overlay should be darkened (dimmed) to make the notification card and ad pop.
  - NO photography elements, NO hands, NO table. Just a clean digital graphic.

# LAYOUT RULES:
- You MUST show all 3 panels vertically (top gate, middle lift, bottom in-app).
- Separate sections with a thin white horizontal divider line.
- BRAND INTEGRITY: The {brand_name} branding and logo MUST be of professional marketing quality, with perfectly sharp typography and zero distortion.
- Each ad creative must look like a high-end, newly printed execution, maintaining the brand’s premium identity in every panel.
- No NoBrokerHood logos on any physical surfaces. Only '{brand_name}' branding visible on the ad panels.
- Overall feel: Real, natural, candid, authentic Indian community life.

# Output
Return ONLY JSON:
{{
    "industry_analysis": "Short note",
    "subject": "Strategic partnership subject line",
    "email_body": "The email content starting from 'Hi' and ending at the CTA only. Do NOT include any signature or closing name here.",
    "image_prompt": "The detailed 3-panel high-realism vertical composite prompt"
}}

<TRANSCRIPT>
{transcript_text}
</TRANSCRIPT>
"""

def strip_gemini_signature(text):
    if not isinstance(text, str):
        return ""
    # WE REMOVED 'NoBrokerHood' from here because it's in the intro text
    signature_patterns = [
        r"Best regards,.*", r"Sincerely,.*", r"Best,.*", r"Thanks,.*",
        r"Regards,.*", r"Warmly,.*", r"Kind regards,.*",
        r"Bhargav Kulkarni.*",
        r"Brand Partnerships & Alliances.*",
        r"\+\d{1,3}\s?\d{10,12}.*",
        r"---", r"__",
    ]
    cleaned = text
    for pattern in signature_patterns:
        # Only strip if it's towards the end of the text (last 100 characters)
        match = re.search(pattern, cleaned, flags=re.IGNORECASE | re.DOTALL)
        if match and match.start() > (len(cleaned) * 0.5): # Only strip if in second half
            cleaned = cleaned[:match.start()].strip()
            
    return cleaned

def generate(brand_name, client_attendees, transcript_text, max_retries=3):
    # Extract name from attendees
    full_client_name = "Client"
    try:
        clean_attendees = client_attendees.replace("[","").replace("]","").replace("'","").replace('"', "")
        attendees = [a.strip() for a in clean_attendees.split(",") if a.strip()]
        if attendees:
            original_name = attendees[0]
            if "@" in original_name:
                full_client_name = original_name.split("@")[0].replace(".", " ").title()
            else:
                full_client_name = original_name
    except:
        pass

    prompt = PROMPT_TEMPLATE.format(
        brand_name=brand_name,
        full_client_name=full_client_name,
        transcript_text=transcript_text
    )

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=config.PRIMARY_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            if response.text:
                data = json.loads(response.text)
                if "email_body" in data:
                    data["email_body"] = strip_gemini_signature(data["email_body"])
                return data

        except Exception as e:
            error_str = str(e)
            if "429" in error_str and "RESOURCE_EXHAUSTED" in error_str:
                print(f"[RATE LIMIT] Hit for {brand_name}. Waiting 5s...")
                time.sleep(5)
                continue
            elif "EOF" in error_str or "getaddrinfo failed" in error_str:
                print(f"[NETWORK ERROR] {brand_name} (attempt {attempt}/{max_retries}). Retrying in 5s...")
                time.sleep(5)
            else:
                print(f"[GEMINI ERROR] {brand_name}: {e}")
                return None

    return None
