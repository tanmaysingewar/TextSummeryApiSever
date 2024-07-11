from fastapi import FastAPI,File,UploadFile,Form
from pydantic import BaseModel
from typing_extensions import Annotated

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import JSONFormatter
from youtube_transcript_api.formatters import TextFormatter


import os
from groq import Groq
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


from langchain_text_splitters import RecursiveCharacterTextSplitter

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import StorageContext, load_index_from_storage

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

import random
import re

from sklearn.cluster import KMeans
import numpy as np




from docx import Document
from PyPDF2 import PdfReader
from pathlib import Path

UPLOAD_DIR = Path() / "upload"

client = Groq(
    api_key="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",
)

embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def read_root():
    print("Health Check")
    return {"status": "ok"}


def extract_text_from_pdf(file_path):
    reader = PdfReader(file_path)
    number_of_pages = len(reader.pages)
    text = ""
    for page in reader.pages:
        text += page.extract_text()
    os.remove(file_path)
    return text

def extract_text_from_docx(file_path):
    doc = Document(file_path)
    para = doc.paragraphs
    text = ""
    for p in para:
        text += p.text
    os.remove(file_path)
    return text

def extract_text_from_txt(file_path):
    with open(file_path, "r") as f:
        text = f.read()
    os.remove(file_path)
    return text

class DocumentStore:
    def __init__(self):
        self.documents = []
        self.vectorizer = TfidfVectorizer()
        self.document_matrix = None

    def add_document(self, text):
        new_chunks = chunk_text(text)
        self.documents.extend(new_chunks)
        self.document_matrix = self.vectorizer.fit_transform(self.documents)

    def query(self, userPrompt, top_k=5):
        if not self.documents:
            return []

        query_vector = self.vectorizer.transform([userPrompt])
        similarities = cosine_similarity(query_vector, self.document_matrix).flatten()
        indices = similarities.argsort()[-top_k:][::-1]
        return [self.documents[i] for i in indices]

store = DocumentStore()

@app.post("/summarize")
async def file_summary(
    upload_file: Annotated[UploadFile, File()],
    userPrompt: Annotated[str, Form()] = None):
    try:
        file_read = await upload_file.read()
        file_path = os.path.join(UPLOAD_DIR, upload_file.filename)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(file_read)

        if upload_file.filename.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        elif upload_file.filename.endswith(".docx"):
            text = extract_text_from_docx(file_path)
        elif upload_file.filename.endswith(".txt"):
            text = extract_text_from_txt(file_path)
        else:
            return {"error": "Unsupported file type"}
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            length_function=len,
            is_separator_regex=False,
        )

        chunk = text_splitter.create_documents([text])

        combined_text = ""
        for i in range(4):
            combined_text += str(random.choice(chunk))

        
        content = (
            f"Instruction: You are a summary generator, your job is to generate a summary of the given data. "
            f"You have to follow the instructions given on how to generate the summary. If no instruction is given, "
            f"then just generate the summary. Data: {combined_text} Instruction: {userPrompt} "
            f"Instruction: The summary should be at least 200 words long."
        )

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": content}],
            model="llama3-70b-8192",
        )

        return chat_completion.choices[0].message.content
    except Exception as e:
        return {"error": str(e)}


@app.post("/chat")
async def file_chat(
    upload_file: Annotated[UploadFile, File()],
    userPrompt: Annotated[str, Form()] = None):
    try:
        file_read = await upload_file.read()
        file_path = os.path.join(UPLOAD_DIR, upload_file.filename)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(file_read)

        if upload_file.filename.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        elif upload_file.filename.endswith(".docx"):
            text = extract_text_from_docx(file_path)
        elif upload_file.filename.endswith(".txt"):
            text = extract_text_from_txt(file_path)
        else:
            return {"error": "Unsupported file type"}

            # load_index_from_storage() missing 1 required positional argument: 'storage_context'

        index = VectorStoreIndex.from_vector_store(vector_store)
        query_engine = index.as_query_engine()

        response = query_engine.query(userPrompt)

        content = (
            f"Instruction: You are a Q&A solver. Here is your information: Data: {response} Using this information, answer the following question: Question: {userPrompt} Instruction: Answer the question using the information provided in the data."
        ) 

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": content}],
            model="llama3-70b-8192",
        )

        return chat_completion.choices[0].message.content
    except Exception as e:
        return {"error": str(e)}



@app.post("/quiz")
async def quiz(
    upload_file: Annotated[UploadFile, File()]):
    try:
        file_read = await upload_file.read()
        file_path = os.path.join(UPLOAD_DIR, upload_file.filename)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(file_read)

        if upload_file.filename.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        elif upload_file.filename.endswith(".docx"):
            text = extract_text_from_docx(file_path)
        elif upload_file.filename.endswith(".txt"):
            text = extract_text_from_txt(file_path)
        else:
            return {"error": "Unsupported file type"}

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            length_function=len,
            is_separator_regex=False,
        )

        chunk = text_splitter.create_documents([text])

        combined_text = ""
        for i in range(4):
            combined_text += str(random.choice(chunk))


        content = (
            f"Generate a quiz based on the following information: Data: {combined_text} "
            f"Instructions :"
            f"1. Generate a quiz based on the given information."
            f"2. The quiz should be at least 10 questions long."
            f"3. The quiz should be in the form of a list of questions and options."
            f"Format of the quiz:"
            f"Each question should be start with **Question :***"
            f"Option should be start with **Option :***"
            f"Each answer should be like **Answer :*** and only give the option number for the answer"
            f"Options: 1, 2, 3, 4"
            f"Answer: Answer"
        ) 

        chat_completion = client.chat.completions.create(
            messages=[{"role": "user", "content": content}],
            model="llama3-70b-8192",
        )

        
        def parse_quiz(response):
            question_blocks = re.split(r"\*\*Question \d+:\*\*", response)[1:]
            parsed_quiz = []

            for block in question_blocks:
                question_match = re.search(r"^(.*?)\n", block)
                question_text = question_match.group(1).strip() if question_match else block.strip()
                
                options = re.findall(r"\*\*Option (\d+):\*\* (.*?)\n", block)
                formatted_options = [f"{opt[1]}" for opt in options]

                
                answer_match = re.search(r"\*\*Answer:\*\* (\d+)", block)
                answer_option = answer_match.group(1) if answer_match else ""

                parsed_quiz.append({
                    "question": question_text,
                    "options": formatted_options,
                    "answer": answer_option
                })

            return parsed_quiz

        
        print(chat_completion.choices[0].message.content)
        # print the parsed quiz its array of questions and options
        json_format =  parse_quiz(chat_completion.choices[0].message.content) 


        json_compatible_item_data = jsonable_encoder(json_format)
        print(json_compatible_item_data)
        return JSONResponse(content=json_compatible_item_data)

    except Exception as e:
        print(e)
        return {"error": str(e)}

        
        
