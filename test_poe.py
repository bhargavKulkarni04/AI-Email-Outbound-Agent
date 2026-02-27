
import os
import config
import generate_email
from google import genai
from google.genai import types

client = genai.Client(api_key=config.GEMINI_API_KEY)

def test_poe_prompt(brand_name, transcript):
    print(f"Testing POE prompt for {brand_name}...")
    data = generate_email.generate(brand_name, "Client Contact", transcript)
    if not data:
        print("Failed to generate data")
        return
    
    print(f"Generated Subject: {data['subject']}")
    print(f"Target Asset: {data['target_asset']}")
    print(f"Image Prompt: {data['image_prompt']}")
    
    filename = f"poe_test_{brand_name.lower().replace(' ', '_')}.png"
    try:
        response = client.models.generate_content(
            model=config.IMAGE_MODEL,
            contents=data['image_prompt'],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    with open(filename, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"Saved {filename}")
                    return
        print("No image in response")
    except Exception as e:
        print(f"Error generating image: {e}")

if __name__ == "__main__":
    test_poe_prompt("Zepto", "We discussed quick delivery slots and gate branding for Zepto. The client wants to target high-intent households during peak morning hours.")
    test_poe_prompt("HDFC Bank", "HDFC wants to promote premium credit cards to lift users and through in-app banners.")
