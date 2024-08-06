import requests

url = "https://api.perplexity.ai/chat/completions"

payload = {
    "model": "mixtral-8x7b-instruct",
    "messages": [
        {
            "role": "user",
            "content": "How many stars are there in our galaxy?"
        }
    ]
}
headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": "Bearer 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"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)