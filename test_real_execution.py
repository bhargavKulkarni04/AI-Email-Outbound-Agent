
import os
import config
import generate_email
from google import genai
from google.genai import types
import time

client = genai.Client(api_key=config.GEMINI_API_KEY)

def test_execution_style(brand_name, transcript):
    print(f"Generating Real Execution style for {brand_name}...")
    # Use the logic from generate_email to get a prompt
    data = generate_email.generate(brand_name, "Client Stakeholder", transcript)
    
    if not data or "image_prompt" not in data:
        print(f"Failed to get prompt for {brand_name}")
        return

    prompt = data["image_prompt"]
    filename = f"execution_test_{brand_name.lower().replace(' ', '_')}.png"
    
    try:
        response = client.models.generate_content(
            model=config.IMAGE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    with open(filename, "wb") as f:
                        f.write(part.inline_data.data)
                    print(f"Successfully saved: {filename}")
                    print(f"Prompt used: {prompt[:100]}...")
                    return True
        print("No image found in response.")
    except Exception as e:
        print(f"Error for {brand_name}: {e}")
    return False

if __name__ == "__main__":
    test_cases = [
        ("Zepto", "Discussed 10-minute grocery delivery targeting residents in premium lifts. Focus on fresh vegetables and monthly savings."),
        ("Asian Paints", "Interested in gate branding for society entrance. Showcase beautiful home transformations and professional painting services."),
        ("Tata Motors EV", "Wants to showcase the new electric SUV at premium society gates to target eco-conscious families."),
        ("Starbucks", "Promote morning coffee and snack deals for busy professionals using elevator lift panels between 8 AM and 11 AM."),
        ("Dyson", "Showcase air purifiers in society lobbies and digital notice boards, focusing on clean air for children and elderly.")
    ]
    
    for brand, transcript in test_cases:
        test_execution_style(brand, transcript)
        time.sleep(2) # Avoid immediate rate limits
