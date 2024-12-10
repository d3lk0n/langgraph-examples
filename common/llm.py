from openai import OpenAI
from os import environ
from dotenv import load_dotenv


load_dotenv() # create .env file locally

openai_api_key = environ.get('OPENAI_API_KEY') # Set up with the API key provided by your professor
openai_api_base = environ.get('OPENAI_API_BASE') # Set up with the URL provided by your professor
model_name = environ.get("MODEL_NAME") # Set up with the currently deployed model (check via HTTP GET to BASE_URL + "/v1/models")

client = OpenAI(
    api_key=openai_api_key,
    base_url=openai_api_base,
)

chat_response = client.chat.completions.create(
    model=model_name,
    messages=[
        {"role": "system", "content": """You are a Named Entity Recognition Tool.
Recognize named entities and output the structured data as a JSON. **Output ONLY the structured data.**
Below is a text for you to analyze."""},
        {"role": "user", "content": "My name is John Doe and I live in Berlin, Germany."},
    ]
)

print(chat_response.choices[0].message.content)
