
import os
import config
from google import genai
from google.genai import types

client = genai.Client(api_key=config.GEMINI_API_KEY)

def generate_demo(brand_name, asset_desc, filename):
    try:
        refined_prompt = f"""
        STYLE: High-end, ultra-realistic architectural photograph. Professional lighting, shallow depth of field, authentic environmental textures. 
        CONTEXT: A premium luxury Indian gated community (Bangalore/Mumbai style). Lush greenery and modern stone/glass architecture in the background.
        HUMAN PRESENCE: A resident is partially visible in the blurred background, naturally walking toward their car. They are NOT looking at the ad.
        ASSET: {asset_desc}
        AD CONTENT: A high-fidelity, premium advertisement for '{brand_name}'. 
        NO EXTERNAL BRANDING: Absolutely no NoBrokerHood logos or mentions.
        EMOTION: Modern, aspirational, and authentic Indian lifestyle.
        """

        print(f"Generating Premium Demo for {brand_name}...")
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
    # Demo 1: The 'Thick Board' Gate Branding (The one you really care about)
    generate_demo(
        "Dyson India", 
        "GATE BRANDING: A 1-inch THICK SOLID SUNBOARD mounted with professional clamps to a heavy black metal society gate. The print is high-quality vinyl with a matte finish.", 
        "premium_dyson_gate.png"
    )
    # Demo 2: The 'Metal Frame' Lift Branding
    generate_demo(
        "Starbucks India", 
        "LIFT BRANDING: A professional vertical poster inside a polished metallic frame on a brushed stainless steel elevator wall.", 
        "premium_starbucks_lift.png"
    )
    # Demo 3: The 'Modern Kiosk'
    generate_demo(
        "Rolex", 
        "KIOSK: A sleek, high-end digital kiosk unit standing in a sunlit marble society lobby.", 
        "premium_rolex_lobby.png"
    )
