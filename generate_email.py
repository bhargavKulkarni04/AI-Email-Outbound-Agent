
"""
Generate Email Module
Uses Gemini 2.5 Flash to create Follow-up email based on real meeting transcript.
"""

import re
import json
import time
import os
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

# STAGE 2: THE EMAIL (ULTRA-MINIMAL SOLUTION STRUCTURE)
Generate the email content based on the <TRANSCRIPT> following these exact guidelines:

1. SUBJECT: Provide exactly ONE high-impact subject line. Do not use spam words. You MUST draw inspiration from or use one of these best-practice styles:
      - "Capturing the resident journey: Re-imagining {brand_name}’s presence from gate to door"
      - "Dominating the daily flow: A 360-degree society branding strategy for {brand_name}"
      - "Bringing {brand_name} to life inside India's most premium gated communities"
      - "Beyond the city noise: Engaging {brand_name} with homeowners at the point of intent"
      - "Precision targeting: Taking {brand_name} directly to the residents of elite society clusters"
      - "Building long-term community recall for {brand_name} within high-intent resident apps"
      - "A first look: How {brand_name} integrates into our premium lift and gate inventory"
      - "Next steps for the {brand_name} pilot: Mapping the roadmap for direct resident engagement"
      - "Meeting {brand_name} halfway: Integrating into the residents' daily home-delivery journey"
      - "Direct-to-home visibility: Why {brand_name} belongs inside the resident's daily lifestyle"
      - "Precision targeting: Taking {brand_name} directly to the residents of elite society clusters"
      - "Building long-term community recall for {brand_name} within high-intent resident apps"
      - "Dominating the gate-to-lift journey: A 360-degree branding strategy for {brand_name}"

2. EMAIL BODY (MINIMAL & DIRECT):
   - GREETING: If {full_client_name} is "Client", start the email with "Hi,". If it is a real name, use "Hi {full_client_name},".
   - OPENING (3 Lines): Jump directly into what was discussed in the meeting. Pull 3 specific points from the <TRANSCRIPT> — mention the exact product, city, problem, or strategy that was talked about. Do NOT use generic phrases like 'great discussion', 'insightful conversation', 'productive meeting', 'was insightful', 'Thank you for your time'. Start with something like 'Our discussion on identifying the right society clusters for {brand_name} in [city]...' and continue for 3 lines with real meeting details.
   
   - SOCIETY-FIRST SOLUTIONS (Select 2): Identify 2 key blockers or concerns from the <TRANSCRIPT> and map them to the most relevant titles from the menu below. Use THIS format (one per line):
     - **Society-First Title** : [One-line solution using terms from JARGON_GLOSSARY]. (Keep the description concise and punchy).

     SOCIETY-FIRST TITLE MENU (Select 2 most relevant):
     - **Premium Society Customization** : Our platform allows us to bypass general city noise by filtering specific clusters with flat valuations above 2-3 Crores, ensuring your brand reaches only the most affluent resident owners.
     - **High-Intent Resident Engagement** : Drive sales and conversion-focused offers via strategic Post Approval Card (PAC) notifications.
     - **Society Cluster Performance** : We will establish clear performance metrics for your 30-day pilot across specific society tiers, validating high-efficiency acquisition.
     - **Direct-to-Home Delivery Focus** : We leverage our Post-Approval Screen (PAC) to capture intent at the exact moment a resident expects a delivery, converting passive interest into direct sales.
     - **Gate-to-Lift Branding Impact** : By synchronizing physical Gate Branding with high-visibility Elevator Panels, we create a continuous 360-degree presence for residents from the moment they enter the society until they reach their door.
     - **Top-of-Mind Resident Presence** : Achieve consistent community-level brand recall through integrated in-society touchpoints.

   - INDUSTRY PROOF: Use this EXACT sentence: "{relevant_study}".

   - FINAL SECTION (DIVIDER BOX): You MUST include the section below exactly as formatted here:
     ________________________________________________
     Explore our offerings: <a href="https://www.canva.com/design/DAGfKxefahY/sg1k0ES4y3phNe_vE35hrQ/view?utm_content=DAGfKxefahY&utm_campaign=designshare&utm_medium=link2&utm_source=uniquelinks&utlId=h3fc1bc71be#1">NoBrokerHood Brand Partnerships</a>

     Let's schedule a 10-minute call next week to discuss the specific society clusters for your pilot.
     ________________________________________________
     
     this is how **{brand_name}** looks in premium society

3. STYLE GUIDELINES (STRICT):
   - NO CORPORATE JARGON: NEVER use titles like "Audience Precision", "Direct Conversions", "Need for Direct Conversions", "Campaign Performance", or "Proving Pilot ROI".
   - MINIMAL CONTENT: The entire email MUST be short and punchy. No generic fluff.
   - DOUBLE SPACING: Use clear double-line breaks (empty lines) between the opening paragraph, the society solutions section, the industry proof line, and the action/closing section.
   - NO SIGNATURE: The systems handles the signature. Do not include "Regards", "Best", or any name at the end.

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
    "industry_analysis": "Short note about brand objectives",
    "subject": "The single high-impact subject line following the guidelines above exactly.",
    "email_body": "The minimal email content following the guidelines above exactly.",
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
        r"---",
    ]
    cleaned = text
    for pattern in signature_patterns:
        # Only strip if it's towards the end of the text (last 100 characters)
        match = re.search(pattern, cleaned, flags=re.IGNORECASE | re.DOTALL)
        if match and match.start() > (len(cleaned) * 0.5): # Only strip if in second half
            cleaned = cleaned[:match.start()].strip()
            
    return cleaned

def generate(brand_name, client_attendees, transcript_text, industry=None, max_retries=3):
    # Load case studies
    case_studies = []
    try:
        with open(os.path.join(os.path.dirname(__file__), "case_studies.json"), "r") as f:
            case_studies = json.load(f)
    except Exception as e:
        print(f"[ERROR] Could not load case_studies.json: {e}")

    # Find a relevant case study
    relevant_study = "We have partnered with similar premium brands to drive premium visibility and in-store footfall within our societies."
    if industry:
        # Try to find matches in our JSON or a fallback
        brand_names = []
        for s in case_studies:
            if str(s.get("Industry")).lower() == industry.lower() and s.get("Brand"):
                b_name = s.get("Brand").strip()
                if b_name.lower() != brand_name.lower() and b_name not in brand_names:
                    brand_names.append(b_name)
                if len(brand_names) == 2:
                    break
        
        if len(brand_names) == 2:
            relevant_study = f"We have partnered with similar leading brands like **{brand_names[0]}** and **{brand_names[1]}** to drive premium visibility and in-store footfall within our societies."
        elif len(brand_names) == 1:
            relevant_study = f"We have partnered with similar leading brands like **{brand_names[0]}** to drive premium visibility and in-store footfall within our societies."

    # Extract name from attendees
    full_client_name = "Client"
    try:
        clean_attendees = client_attendees.replace("[","").replace("]","").replace("'","").replace('"', "")
        attendees = [a.strip() for a in clean_attendees.split(",") if a.strip()]
        if attendees:
            original_name = attendees[0]
            if "@" in original_name:
                name_part = original_name.split("@")[0]
                parts = re.split(r'[\._]', name_part)
                full_client_name = " ".join([p.capitalize() for p in parts if p])
            else:
                full_client_name = original_name
    except:
        pass

    prompt = PROMPT_TEMPLATE.format(
        brand_name=brand_name,
        full_client_name=full_client_name,
        transcript_text=transcript_text,
        relevant_study=relevant_study
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
