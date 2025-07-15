import os
import json
import time
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
    """Generates product description + attributes using OpenAI with fallback to JSON parsing."""
    is_set = "SET" in style_number.upper()
    set_text = "This style is a coordinated clothing set." if is_set else ""
    keyword_list = ", ".join(keywords[:3])

    formatted_prompt = generate_description_prompt.format(
        style_number=style_number,
        keywords=keyword_list,
        set_text=set_text,
        extracted_text=text
    ) + f"\nEnsure the keywords ({keyword_list}) are included naturally in the description."

    for attempt in range(max_retries):
        try:
            print(f"\n🔍 DEBUG: Sending request to OpenAI (function-call) for {style_number}...")

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a fashion copywriter."},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": formatted_prompt},
                            *[{"type": "image_url", "image_url": {"url": url}} for url in images]
                        ]
                    }
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "generate_product_description",
                            "description": "Generate a fashion product description and attributes",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "product_title": {"type": "string"},
                                    "description": {"type": "string"},
                                    "product_category": {"type": "string"},
                                    "product_type": {"type": "string"},
                                    "key_attribute": {"type": "string"},
                                    "hashtags": {
                                        "type": "array",
                                        "items": {"type": "string"}
                                    },
                                    "attributes": {
                                        "type": "object",
                                        "properties": {
                                            "fabric": {"type": "string"},
                                            "silhouette": {"type": "string"},
                                            "length": {"type": "string"},
                                            "neckline": {"type": "string"},
                                            "sleeve": {"type": "string"}
                                        }
                                    }
                                },
                                "required": [
                                    "product_title",
                                    "description",
                                    "product_category",
                                    "product_type"
                                ]
                            }
                        }
                    }
                ],
                tool_choice={
                    "type": "function",
                    "function": {"name": "generate_product_description"}
                }
            )

            print(f"🧪 DEBUG RAW RESPONSE: {response}")

            # ✅ Prefer tool_calls; fallback to raw text if missing
            if response.choices[0].message.tool_calls:
                arguments = response.choices[0].message.tool_calls[0].function.arguments
                parsed_data = json.loads(arguments)
            else:
                raw_text = response.choices[0].message.content.strip()
                print("⚠️ No tool_calls returned. Falling back to plain JSON text parsing...")
                parsed_data = json.loads(raw_text)

            # ✅ Clean + truncate fields
            description = parsed_data.get("description", "").replace("\n", " ").strip()
            if len(description) > 300:
                print(f"⚠️ Truncating long description for {style_number}.")
                description = description[:297].rstrip() + "..."

            product_title = parsed_data.get("product_title", "").strip()
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
            used_keywords = [kw for kw in keywords if kw.lower() in description.lower()]
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

        except json.JSONDecodeError as je:
            print(f"❌ JSON Decode Error in attempt {attempt+1} for {style_number}: {je}")
            time.sleep(2)
        except Exception as e:
            print(f"❌ ERROR in attempt {attempt+1} for {style_number}: {e}")
            time.sleep(2)

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
