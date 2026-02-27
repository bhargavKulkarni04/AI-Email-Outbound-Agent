
import generate_email
import json

brand_name = "Tata Motors EV"
client_attendees = "Anjali Sharma (Marketing Head)"
transcript = "Anjali mentioned that Tata is specifically looking for high-visibility spots to showcase their new Nexon EV. They want to reach eco-conscious families who live in high-rise apartments in Mumbai and show them how the EV charging infrastructure can be promoted within their society gated community. They are moving away from traditional TV ads to more ground-level execution where the car is seen as part of their lifestyle."

print("Testing Finalized Expert Logic...")
result = generate_email.generate(brand_name, client_attendees, transcript)

if result:
    print("\n[SUCCESS] Content generated.")
    print("\n--- Industry Analysis ---")
    print(result.get("industry_analysis"))
    print("\n--- Subject ---")
    print(result.get("subject"))
    print("\n--- Email Body ---")
    print(result.get("email_body"))
    print("\n--- Image Prompt Check ---")
    prompt = result.get("image_prompt", "")
    if "TOP SECTION — GATE BRANDING" in prompt and "BOTTOM SECTION — DIGITAL IN-APP (PAC)" in prompt:
        print("PASS: Image prompt contains correct structural markers.")
    else:
        print("FAIL: Image prompt structure is incorrect.")
else:
    print("[ERROR] Failed to generate content.")
