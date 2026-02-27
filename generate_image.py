
"""
Generate Image Module
Uses Gemini 3 Pro Image Preview (Nano Banna Pro) to create a custom brand mockup.
Since this is a Gemini model (not Imagen), we use generate_content with image output.
"""

import base64
from google import genai
from google.genai import types
import config

client = genai.Client(api_key=config.GEMINI_API_KEY)


def create_mockup(brand_name, image_prompt):
    """
    Generates a mockup image using Gemini 3 Pro Image Preview.
    Returns raw image bytes, or None if it fails.
    """
    try:
        print(f"[IMAGE] Generating mockup for {brand_name}...")
        response = client.models.generate_content(
            model=config.IMAGE_MODEL,
            contents=image_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"]
            )
        )

        # Extract image from response parts
        if response.candidates:
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    print(f"[IMAGE] Mockup ready for {brand_name}")
                    return part.inline_data.data

        print(f"[WARN] No image generated for {brand_name}")
    except Exception as e:
        print(f"[WARN] Image generation failed for {brand_name}: {e}")

    return None
