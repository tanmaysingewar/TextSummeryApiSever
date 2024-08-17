import requests
import os
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
load_dotenv()

url = "https://api.perplexity.ai/chat/completions"

def chat_completion(prompt):
    print(prompt)
    payload = {
        "model": "llama-3.1-8b-instruct",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "authorization": f"Bearer {os.getenv('PERPLEXITY_API_KEY')}"
    }

    response = requests.post(url, json=payload, headers=headers)
    print(response.status_code)

    if response.status_code == 200:
        json_response = response.json()
        return json_response.get("choices")[0].get("message").get("content")
    elif response.status_code == 429:
        return response.status_code
    elif response.status_code == 400:
        return response.status_code
    else:
        return False

__all__ = ["chat_completion"]