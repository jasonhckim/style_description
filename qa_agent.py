import os
import json
import yaml
import openai
from dotenv import load_dotenv
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.chat.completions.create(
  model="gpt-4",
  messages=[{"role": "user", "content": "Your prompt here"}],
)

# ✅ Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# ✅ Load YAML prompt config
with open("QA_Agent.yaml", "r") as f:
    prompt_config = yaml.safe_load(f)

PROMPT = prompt_config["review_and_optimize_descriptions_prompt"]

# ✅ Load descriptions from JSON file (or define inline)
INPUT_FILE = "input_descriptions.json"
OUTPUT_FILE = "optimized_descriptions.json"

# Fallback input if no file exists
default_input = [
    {
        "product_title": "Chic Velvet Tee",
        "description": "This chic, chic velvet tee is perfect for layering and perfect for any season. A versatile and eye-catching piece."
    }
]

if os.path.exists(INPUT_FILE):
    with open(INPUT_FILE, "r") as f:
        input_descriptions = json.load(f)
else:
    input_descriptions = default_input

# ✅ Process each product with OpenAI
optimized_results = []
for item in input_descriptions:
    user_prompt = f"""{PROMPT}

Input:
{json.dumps(item, ensure_ascii=False)}
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a product copy editor."},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.5
        )

        result = response["choices"][0]["message"]["content"]
        try:
            json_output = json.loads(result)
            optimized_results.append(json_output)
        except json.JSONDecodeError:
            print("⚠️ Failed to parse response as JSON:", result)

    except Exception as e:
        print("❌ OpenAI API error:", e)

# ✅ Save optimized output
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    json.dump(optimized_results, f, ensure_ascii=False, indent=2)

print(f"✅ Optimized {len(optimized_results)} descriptions saved to {OUTPUT_FILE}")
