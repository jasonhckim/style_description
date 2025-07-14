import os
import json
import time
import re
import yaml
from openai import OpenAI

# ✅ Load prompts from YAML
try:
    with open("openai_prompts.yaml", "r") as f:
        prompts = yaml.safe_load(f)
    generate_description_prompt = prompts["generate_description_prompt"]
except FileNotFoundError:
    print("❌ ERROR: openai_prompts.yaml not found. Check the file path.")
    exit(1)
except KeyError:
    print("❌ ERROR: 'generate_description_prompt' key missing in openai_prompts.yaml.")
    exit(1)

# ✅ Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def generate_description(style_number, images, keywords, text, max_retries=3):
    """Generates product description + attributes using OpenAI."""
    is_set = "SET" in style_number.upper()
    set_text = "This style is a coordinated clothing set." if is_set else ""

    keyword_list = ", ".join(keywords[:3])  # use top 3 keywords

    # ✅ Format full prompt
    formatted_prompt = generate_description_prompt.format(
        style_number=style_number,
        keywords=keyword_list,
        set_text=set_text,
        extracted_text=text
    ) + f"""
    
Respond only in this strict JSON format:
{{
  "product_title": "...",
  "description": "...",
  "product_category": "...",
  "product_type": "...",
  "key_attribute": "...",
  "hashtags": ["...", "..."],
  "attributes": {{
    "fabric": "...",
    "silhouette": "...",
    "length": "...",
    "neckline": "...",
    "sleeve": "..."
  }}
}}

Ensure the keywords ({keyword_list}) are included naturally in the description.
"""

    for attempt in range(max_retries):
        try:
            print(f"\n🔍 DEBUG: Sending request to OpenAI for {style_number}...")

            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    {"role": "system", "content": "You are a fashion copywriter. Reply only with JSON, no extra text."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": formatted_prompt},
                            *[{"type": "image_url", "image_url": {"url": url}} for url in images]
                        ]
                    }
                ]
            )

            raw_text = response.choices[0].message.content.strip()
            print(f"\n🧪 RAW RESPONSE:\n{raw_text}\n")

            # ✅ Extract JSON block safely
            if not raw_text.startswith("{"):
                print(f"❌ Response does not start with '{{'. Skipping.")
                continue

            match = re.search(r"\{[\s\S]*\}", raw_text)
            if not match:
                raise ValueError("No valid JSON object found.")
            raw_json = match.group(0)

            parsed_data = json.loads(raw_json)

            # ✅ Clean and truncate fields
            description = parsed_data.get("description", "").replace("\n", " ").strip()
            if len(description) > 300:
                print(f"⚠️ Truncating long description for {style_number}.")
                description = description[:297].rstrip() + "..."

            product_title = parsed_data.get("product_title", "").replace("\n", " ").strip()
            product_category = parsed_data.get("product_category", "N/A").strip()
            product_type = "Set" if is_set else parsed_data.get("product_type", "N/A").strip()
            key_attribute = parsed_data.get("key_attribute", "N/A").strip()
            hashtags = ", ".join(parsed_data.get("hashtags", []))

            # ✅ Attributes
            attributes = parsed_data.get("attributes", {})
            fabric = attributes.get("fabric", "N/A")
            silhouette = attributes.get("silhouette", "N/A")
            length = attributes.get("length", "N/A")
            neckline = attributes.get("neckline", "N/A")
            sleeve = attributes.get("sleeve", "N/A")

            # ✅ Keyword usage tracking
            used_keywords = [kw for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', description, re.IGNORECASE)]
            used_keywords_str = ", ".join(used_keywords)

            return {
                "Style Number": style_number,
                "Product Title": product_title,
                "Product Description": description,
                "Tags": hashtags,
                "Product Category": product_category,
                "Product Type": product_type,
                "Option2 Value": key_attribute,
                "Keywords": used_keywords_str,
                "Fabric": fabric,
                "Silhouette": silhouette,
                "Length": length,
                "Neckline": neckline,
                "Sleeve": sleeve
            }

        except Exception as e:
            print(f"❌ ERROR in attempt {attempt+1} for {style_number}: {e}")
            time.sleep(2)

    # ✅ Fallback result if all retries fail
    print(f"❌ FAILED after {max_retries} attempts for {style_number}.")
    return {
        "Style Number": style_number,
        "Product Title": "N/A",
        "Product Description": "Failed to generate description.",
        "Tags": "N/A",
        "Product Category": "N/A",
        "Product Type": "N/A",
        "Option2 Value": "N/A",
        "Keywords": "N/A",
        "Fabric": "N/A",
        "Silhouette": "N/A",
        "Length": "N/A",
        "Neckline": "N/A",
        "Sleeve": "N/A"
    }
