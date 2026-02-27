
import config
from google import genai
from google.genai import types

client = genai.Client(api_key=config.GEMINI_API_KEY)

def generate_vertical_composite(brand_name):
    print(f"Generating 3-in-1 Vertical Composite for {brand_name}...")

    composite_prompt = f"""
    Create a highly realistic vertical collage image split into THREE distinct horizontal sections stacked top to bottom.
    Each section must look like a candid smartphone photo taken inside a standard Indian residential society — NOT ultra-luxury, NOT studio lighting. Use natural, slightly overcast daylight.

    TOP SECTION — GATE BRANDING
    - A standard Indian apartment complex entrance. Black wrought-iron sliding gate.
    - A thin, flat 4ft x 3ft horizontal ACP board displaying a '{brand_name}' ad, mounted on the gate bars. FLAT board, NOT a thick lightbox.
    - Trees and apartment buildings visible naturally in the background.
    - A watchman at the gatehouse casually checking a logbook. A resident walking past in the background, not looking at the ad.

    MIDDLE SECTION — LIFT BRANDING
    - Brushed stainless steel elevator interior with vertical metallic grain texture.
    - An A3 size printed poster in a thin clean white acrylic frame showing the '{brand_name}' ad, mounted on the wall.
    - Elevator buttons and CCTV camera in corner visible.
    - A resident entering the lift holding a grocery bag, a maintenance worker visible in hallway behind — both going about their day.

    BOTTOM SECTION — DIGITAL IN-APP (PAC)
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

    LAYOUT RULES:
    - Stack all three vertically (top gate, middle lift, bottom in-app).
    - Separate sections with a thin white horizontal divider line.
    - BRAND INTEGRITY: The {brand_name} branding and logo MUST be of professional marketing quality, with perfectly sharp typography and zero distortion.
    - Each ad creative must look like a high-end, newly printed execution, maintaining the brand’s premium identity in every panel.
    - No NoBrokerHood logos on any physical surfaces. Only '{brand_name}' branding visible on the ad panels.
    - Overall feel: Real, natural, candid, authentic Indian community life.
    """

    filename = f"composite_v2_{brand_name.lower().replace(' ', '_')}.png"

    try:
        response = client.models.generate_content(
            model=config.IMAGE_MODEL,
            contents=composite_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    with open(filename, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"Saved: {filename}")
                    return True
        print("No image in response.")
    except Exception as e:
        print(f"Error: {e}")
    return False

if __name__ == "__main__":
    generate_vertical_composite("Samsung")
