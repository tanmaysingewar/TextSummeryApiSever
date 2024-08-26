import requests

url = "https://api.perplexity.ai/chat/completions"
models =["llama-3.1-8b-instruct","llama-3.1-sonar-small-128k-online"]
i=0

def dual_model_chat_completion(prompt,i):  
    try :
        payload = {
            "model": models[i],
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
            "authorization": f"Bearer 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" #
        }

        response = requests.post(url, json=payload, headers=headers)

        if response.status_code == 200:
            json_response = response.json()
            return json_response.get("choices")[0].get("message").get("content")
        elif response.status_code == 429:
            return response.status_code
        elif response.status_code == 400:
            return response.status_code
        else:
            return False
    except Exception as e:
        return False

__all__ = ["dual_model_chat_completion"]