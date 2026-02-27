
import os
import config
from google import genai
from google.genai import types

client = genai.Client(api_key=config.GEMINI_API_KEY)

def generate_composite(brand_name):
    print(f"Generating 3-in-1 Composite Mockup for {brand_name}...")
    
    # We describe a triptych layout
    composite_prompt = f"""
    Create a professional 3-panel wide-angle graphic showcasing the '{brand_name}' campaign across three different premium Indian residential assets in a single high-resolution image.
    
    LAYOUT: The image is split into three distinct vertical sections.
    
    SECTION 1 (LEFT): GATE BRANDING
    - A 4x3ft horizontal rectangular ACP board for {brand_name} mounted on a heavy black iron society gate.
    - Authentic Indian society entrance in the background (lush greenery, palm trees).
    
    SECTION 2 (CENTER): LIFT BRANDING
    - An A3 size printed poster for {brand_name} inside a white acrylic frame on a brushed stainless steel elevator wall.
    - Include a small CCTV and subtle metallic reflections.
    
    SECTION 3 (RIGHT): KIOSK/ISLAND BRANDING
    - A premium digital standing kiosk in a sunlit society clubhouse lobby displaying the {brand_name} ad.
    - Modern marble flooring and potted plants in the background.
    
    OVERALL STYLE: High-fidelity smartphone photography, natural daylight, professional installation look, NO rust or dirt. 
    HUMAN ELEMENT: Background residents walking naturally (not looking at ads) to add scale.
    NO BROKERHOOD LOGOS. Only '{brand_name}' should be visible.
    """

    filename = f"composite_mockup_{brand_name.lower()}.png"
    
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
    generate_composite("Samsung")
