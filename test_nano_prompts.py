
import os
import config
from google import genai
from google.genai import types

client = genai.Client(api_key=config.GEMINI_API_KEY)

def generate_demo(brand_name, prompt_text, filename):
    try:
        print(f"Generating demo for {brand_name}...")
        response = client.models.generate_content(
            model=config.IMAGE_MODEL,
            contents=prompt_text,
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

# Demo 1: Lift Branding (Elevator)
lift_prompt = """
A highly realistic, wide-angle photo taken inside a premium residential apartment elevator in India. 
The walls are brushed stainless steel with subtle reflections. 
Mounted at eye-level on the side wall is a vertical rectangular advertising poster for 'Wipro Lighting'. 
The poster shows high-end smart LED home lighting with a warm Indian home interior in the background. 
The colors are vibrant but the lighting in the elevator is natural, slightly fluorescent. 
At the very bottom of the poster frame, there is a small, clear white footer that says 'POWERED BY NOBROKERHOOD'. 
A security CCTV camera is visible in the corner of the elevator ceiling. 
The image looks like an unedited smartphone photo taken by a resident, ultra-realistic, zero cartoonishness.
"""

# Demo 2: Gate Branding (Society Gate)
gate_prompt = """
A highly realistic, eye-level outdoor photo of a gated community entrance in an Indian city like Bangalore or Pune. 
The main gate is made of heavy black metal grill bars. 
Fixed firmly onto the center of the black metal gate is a large horizontal brand poster for 'Tata Motors'. 
The poster features a sleek electric SUV. 
In the background, lush green trees and a modern apartment building are visible. 
The sky is slightly overcast, typical of an Indian afternoon. 
The image captures the texture of the metal gate and the printed vinyl of the poster. 
The overall vibe is a real-life snapshot of an upscale Indian township entrance, hyper-realistic, authentic street photography style.
"""

if __name__ == "__main__":
    generate_demo("Wipro Lighting", lift_prompt, "demo_lift_branding.png")
    generate_demo("Tata Motors", gate_prompt, "demo_gate_branding.png")
