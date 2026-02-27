
import os
import config
import generate_email
from google import genai
from google.genai import types

client = genai.Client(api_key=config.GEMINI_API_KEY)

def test_modified_poe(brand_name, transcript):
    print(f"Testing refined POE prompt for {brand_name}...")
    data = generate_email.generate(brand_name, "Client Contact", transcript)
    if not data:
        print(f"Failed to generate data for {brand_name}")
        return
    
    filename = f"refined_poe_{brand_name.lower().replace(' ', '_')}.png"
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
                    print(f"Prompt used: {data['image_prompt'][:100]}...")
                    return
        print("No image in response")
    except Exception as e:
        print(f"Error generating image for {brand_name}: {e}")

if __name__ == "__main__":
    test_cases = [
        ("Wipro Lighting", "Discussed high-end smart lighting for residential corridors and lobby areas."),
        ("Tata Motors EV", "Showcasing the new electric SUV at the society entrance gate."),
        ("Flipkart Minutes", "Promoting 10-minute delivery services on the society digital notice boards."),
        ("HDFC Home Loans", "Promoting premium home loan rates in the elevator lift frames."),
        ("Curefit", "Discussed on-ground gym activations and digital banners for health coaching.")
    ]
    
    for brand, transcript in test_cases:
        test_modified_poe(brand, transcript)
