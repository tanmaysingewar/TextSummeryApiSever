import requests
import os
import json

from dotenv import load_dotenv
load_dotenv()

def get_yt_transcript(url):
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }

    body = {
        "videoUrl": url,
        "langCode": "en"
    }

    response = requests.post(os.getenv('YT_API_URL'), headers=headers, json=body)
    print(response.status_code)
    print(response.text)

    # Load the JSON data
    data = response.json()

    # Extract the captions
    captions = data['captions']

    # Extract and concatenate the text from each caption
    transcript = ' '.join(caption['text'] for caption in captions)

    return transcript

__all__ = ["get_yt_transcript"]