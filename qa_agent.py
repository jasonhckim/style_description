import openai
from openai import OpenAI
import os
import json

print("🧠 OpenAI SDK version:", openai.__version__)
print("🧠 OpenAI SDK file path:", openai.__file__)
# Set up the OpenAI client using your API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Load your descriptions file (or create dummy data if needed)
with open("descriptions.json", "r") as f:
    descriptions = json.load(f)

optimized = []

for item in descriptions:
    product_title = item.get("product_title", "")
    description = item.get("description", "")

    # Compose your prompt
    prompt = f"Improve the following product description for SEO and clarity:\n\nTitle: {product_title}\nDescription: {description}"

    # Use the new Chat Completions API
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that improves product descriptions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300,
        )

        improved = response.choices[0].message.content.strip()
        optimized.append({
            "product_title": product_title,
            "original_description": description,
            "optimized_description": improved
        })

    except Exception as e:
        print(f"❌ OpenAI API error: {e}")

# Save optimized descriptions
with open("optimized_descriptions.json", "w") as f:
    json.dump(optimized, f, indent=2)

print(f"✅ Optimized {len(optimized)} descriptions saved to optimized_descriptions.json")
