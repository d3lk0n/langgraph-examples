from openai import OpenAI


openai_api_key = "KEY" # Replace with the API key from a professor
openai_api_base = "http://gpu01.imn.htwk-leipzig.de:8082/v1"

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

chat_response = client.chat.completions.create(
    model="meta-llama/Llama-3.1-8B-Instruct",
    messages=[
        {"role": "system", "content": """You are a Named Entity Recognition Tool.
Recognize named entities and output the structured data as a JSON. **Output ONLY the structured data.**
Below is a text for you to analyze."""},
        {"role": "user", "content": "My name is John Doe and I live in Berlin, Germany."},
    ]
)

print(chat_response.choices[0].message.content)
