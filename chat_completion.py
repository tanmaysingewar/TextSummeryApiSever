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
    "authorization": "Bearer sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)