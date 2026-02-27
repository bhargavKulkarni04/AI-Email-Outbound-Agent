
import os
import config
from google import genai
from google.genai import types

client = genai.Client(api_key=config.GEMINI_API_KEY)

def generate_demo(brand_name, asset_type, prompt_text, filename):
    try:
        refined_prompt = f"""
        STYLE: Raw, unedited smartphone photo taken by a resident. Natural shadows, balanced exposure, zero cinematic lighting.
        CONTEXT: A premium high-end Indian gated community.
        HUMAN PRESENCE: A resident or security guard is visible walking in the background, busy with their phone (NOT looking at the ad). 
        ASSET: {asset_type}
        AD CONTENT: A professional advertisement for '{brand_name}' showing {prompt_text}.
        NO EXTERNAL BRAND IDENTIFICATION: Do NOT include any NoBrokerHood logos on physical gates or walls.
        EMOTION: Authentic, clean, premium Indian township life.
        """

        print(f"Generating realistic demo for {brand_name} ({asset_type})...")
        response = client.models.generate_content(
            model=config.IMAGE_MODEL,
            contents=refined_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    with open(filename, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"Successfully saved {filename}")
                    return True
        print("No image found in response.")
    except Exception as e:
        print(f"Error: {e}")
    return False

if __name__ == "__main__":
    # In-App Example
    generate_demo(
        "Zomato", 
        "IN-APP BANNER: A modern smartphone held in a resident's hand. The screen shows a clean app UI with a 'Zomato' food delivery banner.", 
        "a delicious Indian thali with a bold 'Order Now' button.", 
        "demo_zomato_inapp.png"
    )
    # Kiosk Example
    generate_demo(
        "HDFC Bank", 
        "KIOSK: A free-standing premium digital kiosk stand in a society clubhouse lobby.", 
        "a high-resolution ad for premium credit cards with a golden metallic finish.", 
        "demo_hdfc_kiosk.png"
    )
    # Island Banner Example
    generate_demo(
        "Mercedes-Benz", 
        "ISLAND BANNER: A ground-mounted physical display stand near the society's luxury swimming pool deck.", 
        "a sleek Mercedes sedan with a focus on luxury and performance.", 
        "demo_mercedes_island.png"
    )
