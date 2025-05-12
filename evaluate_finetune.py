import openai
import csv

openai.api_key = os.environ["OPENAI_API_KEY"]

# Set your fine-tuned model ID here
FINE_TUNED_MODEL = "ft:gpt-3.5-turbo:your-org::your-model-id"
BASE_MODEL = "gpt-3.5-turbo"

# List of test prompts (your validation set)
TEST_SET = [
    {
        "style_number": "ABC123",
        "title": "Linen Dress",
        "description": "A lightweight linen dress perfect for summer days.",
        "expected_title": "Lightweight Linen Summer Dress",
        "expected_description": "Stay cool and stylish in this breezy linen summer dress."
    },
    # Add more test rows...
]

def get_completion(model, input_text):
    response = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a fashion copywriter. Write a product title and description."},
            {"role": "user", "content": input_text}
        ]
    )
    return response.choices[0].message["content"]

with open("finetune_eval_results.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Style Number", "Original Title", "Expected Title",
        "Generated Title (Base)", "Generated Title (Fine-tuned)"
    ])

    for item in TEST_SET:
        input_text = f"Style Number: {item['style_number']}\nTitle: {item['title']}\nDescription: {item['description']}"
        base_output = get_completion(BASE_MODEL, input_text)
        finetuned_output = get_completion(FINE_TUNED_MODEL, input_text)

        writer.writerow([
            item["style_number"],
            item["title"],
            item["expected_title"],
            base_output,
            finetuned_output
        ])
