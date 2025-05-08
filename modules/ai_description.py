import os
import json
import time
import re
import yaml
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))  # ✅ Preferred for secrets

# ✅ Load prompts from YAML file
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

def generate_description(style_number, images, keywords, max_retries=3):
    is_set = "SET" in style_number.upper()
    set_text = "This style is a coordinated clothing set." if is_set else ""
    keyword_list = ", ".join(keywords[:3])

    formatted_prompt = generate_description_prompt.format(
        style_number=style_number,
        keywords=keyword_list,
        set_text=set_text
    ) + f"\n\nEnsure that the following keywords are seamlessly included in the description: {keyword_list}. If necessary, rephrase the description naturally to integrate these keywords."

    for attempt in range(max_retries):
        try:
            print(f"\n🔍 DEBUG: Sending request to OpenAI for {style_number}...")

            # ✅ Correct OpenAI SDK usage for v1.13.3
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a fashion expert."},
                    {"role": "user", "content": formatted_prompt}
                ]
            )

            raw_text = response.choices[0].message.content.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
            parsed_data = json.loads(raw_text)

            description = parsed_data.get("description", "").replace("\n", " ").strip()
            product_title = parsed_data.get("product_title", "").replace("\n", " ").strip()
            product_category = parsed_data.get("product_category", "N/A").strip()
            product_type = "Set" if is_set else parsed_data.get("product_type", "N/A").strip()
            key_attribute = parsed_data.get("key_attribute", "N/A").strip()

            used_keywords = [kw for kw in keywords if re.search(rf'\b{re.escape(kw)}\b', description, re.IGNORECASE)]
            used_keywords_str = ", ".join(used_keywords)

            return {
                "Style Number": style_number,
                "Product Title": product_title,
                "Product Description": description,
                "Tags": ", ".join(parsed_data.get("hashtags", [])),
                "Product Category": product_category,
                "Product Type": product_type,
                "Option2 Value": key_attribute,
                "Keywords": used_keywords_str
            }

        except Exception as e:
            print(f"❌ OpenAI API Error for {style_number}: {e}")
            time.sleep(2)

    print(f"❌ ERROR: All {max_retries} attempts failed for {style_number}. Skipping.")
    return {
        "Style Number": style_number,
        "Product Title": "N/A",
        "Product Description": "Failed to generate description.",
        "Tags": "N/A",
        "Product Category": "N/A",
        "Product Type": "N/A",
        "Option2 Value": "N/A",
        "Keywords": "N/A"
    }
