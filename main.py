from fastapi import FastAPI
from pydantic import BaseModel
import os
from groq import Groq
from fastapi.middleware.cors import CORSMiddleware


client = Groq(
    api_key="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",
)

class Docs(BaseModel):
    data : str
    userPrompt : str | None = None

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.post("/summarize")
def create_item(docs: Docs):
    print(docs)

    content = "Give the summery of this information :"+docs.data + "And what expected form the summery answer in last if this is a question,if empty leave it  : " + docs.userPrompt 

    chat_completion = client.chat.completions.create(
    messages=[
        {
            "role": "user",
            "content": content,
        }
    ],
    model="llama3-8b-8192",
)
    return chat_completion.choices[0].message.content