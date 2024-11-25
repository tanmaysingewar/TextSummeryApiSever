from fastapi import FastAPI,File,UploadFile,Form
from pydantic import BaseModel
from typing_extensions import Annotated
from typing import Union

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter

import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from langchain_text_splitters import RecursiveCharacterTextSplitter

import random
import re

from docx import Document
from PyPDF2 import PdfReader
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import traceback

from chat_completion import chat_completion
from dual_model_chat_completion import dual_model_chat_completion

import requests
import json

from get_proxy import get_proxy
from ytTranscript import get_yt_transcript

import redis

from groq import Groq

# Initialize the Groq client
client = Groq(
    api_key="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"  # Replace with your actual API key
)


UPLOAD_DIR = Path() / "upload"


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins= ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class YTTranscript(BaseModel):
    yt_link: str
    title: str
    country : str
    category : str


def chunk_text(text, chunk_size=500):
    words = text.split()
    return [' '.join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]

def extract_video_id(url):
    pattern = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return None

def parse_quiz(response):
    # Split the response based on **Question :** which is the format in the quiz.
    question_blocks = re.split(r"\*\*Question :\*\*", response)[1:]
    parsed_quiz = []

    for block in question_blocks:
        # Extract the question text
        question_match = re.search(r"^(.*?)\n", block)
        question_text = question_match.group(1).strip() if question_match else block.strip()

        # Extract options
        options = re.findall(r"\*\*Option :\*\* (.*?)\n", block)
        formatted_options = [opt for opt in options]

        # Extract the answer
        answer_match = re.search(r"\*\*Answer :\*\* (\d+)", block)
        answer_option = answer_match.group(1) if answer_match else ""

        parsed_quiz.append({
            "question": question_text,
            "options": formatted_options,
            "answer": answer_option
        })

    return parsed_quiz


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

@app.get("/")
def read_root():
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
        
        content = (
            f"Instruction: You are a summary generator, your job is to generate a summary of the given data. "
            f"You have to follow the instructions given on how to generate the summary. If no instruction is given, "
            f"then just generate the summary. Data: {text} Instruction: {userPrompt} "
            f"Instruction: The summary should be at least 200 words long."
        )

        chat_response = chat_completion(content)
        if chat_response == 429:   
            print("Too many requests")
            return JSONResponse({"error": "Too many requests, it pass Request rate limit or Token rate limit"})
        elif chat_response == 400:   
            print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
            return JSONResponse({"error": "Messages have 39388 tokens, which exceeds the max limit of 16384 tokens."})
        elif chat_response == False:   
            print("Error in chat completion")
            return JSONResponse({"error": "Error in generating the summary"})

        return chat_response
    except Exception as e:
        return {"error": "Error occurred while responding to the summary"}

@app.post("/chat")
async def file_chat(
    upload_file: UploadFile = File(...),
    userPrompt: str = Form(None)):
    try:
        # Read and save the uploaded file
        file_read = await upload_file.read()
        file_path = os.path.join(UPLOAD_DIR, upload_file.filename)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(file_read)

        # Extract text based on file type
        if upload_file.filename.endswith(".pdf"):
            text = extract_text_from_pdf(file_path)
        elif upload_file.filename.endswith(".docx"):
            text = extract_text_from_docx(file_path)
        elif upload_file.filename.endswith(".txt"):
            text = extract_text_from_txt(file_path)
        else:
            return JSONResponse({"error": "Unsupported file type"})

        store = DocumentStore()
        
        store.add_document(text)

        if not userPrompt:
            userPrompt = ""

        relevant_chunks = store.query(userPrompt, top_k=5)
        combined_text = " ".join(relevant_chunks)

        content = (
            f"Role: You are the Q&A solver. Here is your information: Data: {combined_text} "
            f"Using this information, answer the following question: Question: {userPrompt} "
            f"Instruction: Answer the question using the information provided in the data."
        )

        chat_response = chat_completion(content)
        if chat_response == 429:   
            print("Too many requests")
            return JSONResponse({"error": "Too many requests, it pass Request rate limit or Token rate limit"})
        elif chat_response == 400:   
            print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
            return JSONResponse({"error": "Messages have 39388 tokens, which exceeds the max limit of 16384 tokens."})
        elif chat_response == False:   
            print("Error in chat completion")
            return JSONResponse({"error": "Error in generating the summary"})
        
        return chat_response
    
    except Exception as e:
        print(e)
        return JSONResponse({"error": "Error occurred while responding to the query"})

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

        content = (
            f"Generate a quiz based on the following information: Data: {text} "
            f"Instructions :"
            f"1. Generate a quiz based on the given information."
            f"2. The quiz should be in the form of a list of questions and options."
            f"3. Ignore the html tags in the data, they should not be included in the quiz."
            f"4. The quiz should be having exactly 10 questions its very very important."
            f"Format of the quiz:"
            f"**Question :** [question text]"
            f"**Option :** 1. [option text]"
            f"**Option :** 2. [option text]"
            f"**Option :** 3. [option text]"
            f"**Option :** 4. [option text]"
            f"**Answer :** [answer number]"
            f"All the quiz should be in the form of the above format only."
            f"Dont add questions on year, month, day, etc."
            f"Each question should be start with **Question :***"
            f"Each Option should be start with **Option :***"
            f"Each answer should be like **Answer :*** and only give the option number for the answer"
            f"All the quiz should be in the form of the above format only."
            f"Dont add questions on year, month, day, etc."
        )  


        quiz_response = chat_completion(content)
        print(quiz_response)
        if quiz_response == 429:   
            print("Too many requests")
            return JSONResponse({"error": "Too many requests, it pass Request rate limit or Token rate limit"})
        elif quiz_response == 400:
            print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
            return JSONResponse({"error": "Exceeds the max limit of tokens."})
        elif quiz_response == False:   
            print("Error in chat completion")
            return JSONResponse({"error": "Error in generating the summary"})

        json_format =  parse_quiz(quiz_response) 
        print(json_format)

        return JSONResponse(content=json_format)
    except Exception as e:
        print(e)
        return {"error": "Error occurred while generating the quiz"}

@app.post("/ytsummarize")
def yt_summary(
    yt_link: Annotated[str, Form()] = None,
    userPrompt: Annotated[str, Form()] = None):
    try:
        if not yt_link:
            return JSONResponse({"error": "YouTube link is required"})

        try:
            transcript = get_yt_transcript(yt_link)
        except Exception as e:
            print(e)
            return {"error": str("Error occurred while retrieving the transcript")}

        content = (
            f"Instruction: You are a YouTube summary generator, your job is to generate a summary of the given data. "
            f"You have to follow the instructions given on how to generate the summary. If no instruction is given, "
            f"then just generate the summary. Data: {transcript} & UserPrompt: {userPrompt} "
            f"Instruction: The summary should be at least 200 words long."
        )
       
        chat_response = chat_completion(content)
        if chat_response == 429:   
            print("Too many requests")
            return JSONResponse({"error": "Too many requests, it pass Request rate limit or Token rate limit"})
        elif chat_response == 400:   
            print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
            return JSONResponse({"error": "Messages have 39388 tokens, which exceeds the max limit of 16384 tokens."})
        elif chat_response == False:   
            print("Error in chat completion")
            return JSONResponse({"error": "Error in generating the summary"})
        
        return chat_response

    except Exception as e:
        print(e)
        return {"error": "Error occurred while responding to the summary"}

@app.post("/ytchat")
async def file_chat(
    yt_link: Annotated[str, Form()] = None,
    userPrompt: Annotated[str, Form()] = None):
    try:
        if not yt_link:
            return JSONResponse({"error": "YouTube link is required"})

        try:
            transcript = get_yt_transcript(yt_link)
        except Exception as e:
            return {"error": str("Could not retrieve a transcript for the video")}

        store = DocumentStore()
        
        store.add_document(transcript)

        if not userPrompt:
            userPrompt = ""

        relevant_chunks = store.query(userPrompt, top_k=5)
        combined_text = " ".join(relevant_chunks)

        content = (
            f"Role: You are the Q&A solver. Here is your information: Data: {combined_text} "
            f"Using this information, answer the following question: Question: {userPrompt} "
            f"Instruction: Answer the question using the information provided in the data."
        )

        chat_response = chat_completion(content)
        if chat_response == 429:   
            print("Too many requests")
            return JSONResponse({"error": "Too many requests, it pass Request rate limit or Token rate limit"})
        elif chat_response == 400:   
            print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
            return JSONResponse({"error": "Messages have 39388 tokens, which exceeds the max limit of 16384 tokens."})
        elif chat_response == False:   
            print("Error in chat completion")
            return JSONResponse({"error": "Error in generating the summary"})
        
        return chat_response
    
    except Exception as e:
        print(e)
        return JSONResponse({"error": "Error occurred while responding to the query"})

@app.post("/ytquiz")
async def quiz(
    yt_link: Annotated[str, Form()] = None,
    userPrompt: Annotated[str, Form()] = None):
    try:
        if not yt_link:
            return JSONResponse({"error": "YouTube link is required"})

        try:
            transcript = get_yt_transcript(yt_link)
        except Exception as e:
            print(e)
            return {"error": str("Error occurred while retrieving the transcript")}

        content = (
            f"Generate a quiz based on the following information: Data: {transcript} "
            f"Instructions :"
            f"1. Generate a quiz based on the given information."
            f"2. The quiz should be in the form of a list of questions and options."
            f"3. Ignore the html tags in the data, they should not be included in the quiz."
            f"4. The quiz should be having exactly 10 questions its very very important."
            f"Format of the quiz:"
            f"**Question :** [question text]"
            f"**Option :** 1. [option text]"
            f"**Option :** 2. [option text]"
            f"**Option :** 3. [option text]"
            f"**Option :** 4. [option text]"
            f"**Answer :** [answer number]"
            f"All the quiz should be in the form of the above format only."
            f"Dont add questions on year, month, day, etc."
            f"Each question should be start with **Question :***"
            f"Each Option should be start with **Option :***"
            f"Each answer should be like **Answer :*** and only give the option number for the answer"
            f"All the quiz should be in the form of the above format only."
            f"Dont add questions on year, month, day, etc."
        )  
        
        quiz_response = chat_completion(content)
        if quiz_response == 429:   
            print("Too many requests")
            return JSONResponse({"error": "Too many requests, it pass Request rate limit or Token rate limit"})
        elif quiz_response == 400:   
            print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
            return JSONResponse({"error": "Messages have 39388 tokens, which exceeds the max limit of 16384 tokens."})
        elif quiz_response == False:   
            print("Error in chat completion")
            return JSONResponse({"error": "Error in generating the summary"})
        
        json_format =  parse_quiz(quiz_response) 

        return JSONResponse(content=json_format)

    except Exception as e:
        print(e)
        return {"error": str("Error occurred while generating the quiz")}

@app.post("/v3/ytQuizAndSummary")
async def v2YTQuizAndSummary(
    item : YTTranscript) :
    try:
        yt_link = item.yt_link
        title = item.title
        country = item.country
        cat = item.category

        if not yt_link:
            return JSONResponse({"error": "YouTube link is required"})

        try : 
            transcript = get_yt_transcript(yt_link)
            text_formatted = transcript
            print(text_formatted)
        except Exception as e:
            print(e)
            transcript = False

        def generate_summary_from_title():
            content = (
                f"You are a Information extractor for information of topic :{title} and shall focus on topic : {title} related to country : {country} and category : {cat}"
                f"Extract information relevant to topic : {title} related to country : {country} and category : {cat} and augment it with your inherent knowledge of topic : {title}"
                f"Instruction: From information extracted generate summary relevant to topic to inform a culturally sophisticated person. It shall be  250 words long and is formatted as follows:"
                f"<p>This paragraph should summarize the key information for topic : {title}.</p>"
                f"<ul>"
                f"  <li>Key point 1</li>"
                f"  <li>Key point 2</li>"
                f"  <li>Key point 3</li>"
                f"  <li>Additional key points as needed</li>"
                f"</ul>"
                f"<p>Concluding remarks or additional summary text.</p>"
                f"Important: Do not include emojis in the summary."
                f"Note: Do not include title in the summary."
            )

            summery_response = chat_completion(content)
            if summery_response == 429:   
                print("Too many requests")
                return 429
            elif summery_response == 400:   
                print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
                return 400
            elif summery_response == False:   
                print("Error in chat completion")
                return False
            return summery_response
        
        def generate_quiz_from_summary(summary):
            content = (
                f"Generate a quiz based on the following information: Data: {summary}  for topic : {title}  related to country : {country} and category : {cat} only"
                f"Instructions :"
                f"1. Generate a quiz based on above data for topic : {title} related to country : {country} and category : {cat} only with questions that test understanding rather than memory."
                f"2. The quiz should be in the form of a list of questions and options."
                f"3. Ignore the html tags in the data, they should not be included in the quiz."
                f"4. The quiz should have exactly 5 questions."
                f"Format of the quiz:"
                f"**Question :** [question text]"
                f"**Option :** [option text]"
                f"**Option :** [option text]"
                f"**Option :** [option text]"
                f"**Option :** [option text]"
                f"**Answer :** [answer number]"
                f"All the quiz should be on the topic : {title}  related to country : {country} and category : {cat} only."
                f"Dont add questions on year, month, day, etc."
                f"Each question should be start with **Question :***"
                f"Each Option should be start with **Option :***, it shall be very different from other options and there shall be only one correct option"
                f"Each answer should be like **Answer :*** and only give the option number for the answer"
                f"make sure there is only one correct answer to each question"
                f"The quiz should be in form of the above format only."
            ) 

            quiz_response = chat_completion(content)
            print(quiz_response)
            if quiz_response == 429:   
                print("Too many requests")
                return 429 
            elif quiz_response == 400:   
                print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
                return 400
            elif quiz_response == False:   
                print("Error in chat completion")
                return False

            json_format =  parse_quiz(quiz_response)
            json_format = json.dumps(json_format)

            return {
                "summery" : summary,
                "quiz" : json_format
            }

        def generate_summary_from_transcript(transcript):
            content = (
                f"You are a Information extractor for information of topic :{title} and shall focus on topic : {title} related to country : {country} and category : {cat}"
                f"Extract information relevant to topic : {title} related to country : {country} and category : {cat} specified in Data: {transcript} and augment it with your inherent knowledge of topic : {title}"
                f"Instruction: From information extracted generate summary relevant to topic to inform a culturally sophisticated person. It shall be  250 words long and is formatted as follows:"
                f"<p>This paragraph should summarize the key information from the data : {transcript} for topic : {title}.</p>"
                f"<ul>"
                f"  <li>Key point 1</li>"
                f"  <li>Key point 2</li>"
                f"  <li>Key point 3</li>"
                f"  <li>Additional key points as needed</li>"
                f"</ul>"
                f"<p>Concluding remarks or additional summary text.</p>"
                f"Important: Do not include emojis in the summary."
                f"Note: Do not include title in the summary."
            )

            summery_response = chat_completion(content)
            summery_response = (
                f"<h2>Title : {title}</h2>"
                f"{summery_response}"
                f"<p>Ready to test your knowledge? Take the quiz now and earn coins and XP!</p>"
            )

            summery_response = chat_completion(content)
            if summery_response == 429:   
                print("Too many requests")
                return 429
            elif summery_response == 400:   
                print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
                return 400
            elif summery_response == False:   
                print("Error in chat completion")
                return False
            return summery_response

        if cat == "music":
            summery_response = generate_summary_from_title()
            summery_response = (
                f"<h2>Title : {title}</h2>"
                f"{summery_response}"
                f"<p>Ready to test your knowledge? Take the quiz now and earn coins and XP!</p>"
            )
            return generate_quiz_from_summary(summery_response)
        else:
            if transcript == False:
                summery_response = generate_summary_from_title()
                summery_response = (
                    f"<h2>Title : {title}</h2>"
                    f"{summery_response}"
                    f"<p>Ready to test your knowledge? Take the quiz now and earn coins and XP!</p>"
                )
                return generate_quiz_from_summary(summery_response)
            else:
                summery_response = generate_summary_from_transcript(transcript)
                if summery_response == 429:   
                    print("Too many requests")
                    return JSONResponse({"error": "Too many requests, it pass Request rate limit or Token rate limit"})
                elif summery_response == 400:   
                    print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
                    title_summery_response = generate_summary_from_title(title)
                    return generate_quiz_from_summary(title_summery_response)
                elif summery_response == False:   
                    print("Error in chat completion")
                    return JSONResponse({"error": "Error in generating the summary"})
                else: 
                    return generate_quiz_from_summary(summery_response)
       
    except Exception as e:
        print(e)
        return {"error": str("Error occurred while generating the quiz and summary")}
        
@app.post("/v4/ytQuizAndSummary")
async def v2YTQuizAndSummary(item : YTTranscript):
    try:
        yt_link = item.yt_link
        title = item.title
        country = item.country
        cat = item.category

        if not yt_link:
            return JSONResponse({"error": "YouTube link is required"})
        try : 
            transcript = get_yt_transcript(yt_link)
            print("transcript generated")
        except Exception as e:
            print("No transcript generated")
            transcript = ""

        def generate_summary(transcript, title, country, cat):
            cat = '. '.join(i.capitalize() for i in cat.split('. '))
            i= 0
            words = title
            try:
                if len(words) < 20 and transcript != "" :
                    i=1
                    content = (
                        f"You provide genuinely correct information of topic:{title} and shall focus on topic: {title} related to country: {country} and category: {cat}"
                        f"Fetch information relevant to topic: {title} related to country: {country} and category: {cat} from your inherent knowledge of topic: {title}"
                        f"Instruction: From information fetched generate summary relevant to topic: {title}. It shall be 250 words long and is formatted as follows:"
                        f"Important: Do not include emojis in the summary."
                        f"Instruction : If provided Data is insufficient then please sticks to facts in data and do not make up sentences"
                        f"Summary shall not contain sentence : This paragraph should summarize the key information from the data."
                        f"Summary shall not contain sentence : Concluding remarks or additional summary text."
                        f"Note: Summary title should not contain the word 'Summary.'"
                        f"Note: Summary title should contain the topic only: {title}"
                        f"""
                        Response should be in HTML format only, with the following structure:
                        <h2>Title : Title of the summary</h2>
                        <p>This paragraph should summarize the key information from the data.</p>
                        <ul>
                            <li>Key point 1</li>
                            <li>Key point 2</li>
                            <li>Key point 3</li>
                            <li>Additional key points as needed</li>
                        </ul>
                        <p>Concluding remarks or additional summary text.</p>
                        """)
                else:
                    if cat in  ['Art', 'Cinema', 'History', 'Literature'] and  transcript != "":
                        content = (
                            f"Instruction: You are a Smart Summary Generator. Your task is to create a comprehensive summary of the provided data only. "
                            f"Follow the specific instructions for generating the summary."
                            f"generate a well-rounded summary from Data: {transcript} only"
                            f"Instruction: Ensure the summary is  200 words long and is formatted as follows:"
                            f"Important: Do not include emojis in the summary."
                            f"Instruction : If provided Data is insufficient then please sticks to facts in data and do not make up sentences"
                            f"Summary shall not contain sentence : This paragraph should summarize the key information from the data."
                            f"Summary shall not contain sentence : Concluding remarks or additional summary text."
                            f"Note: The summary title should not contain the word 'Summary.'"
                            f"Note: Summary title should contain the topic only: {title} "
                            f"""
                            Response should be in HTML format only, with the following structure:
                            <h2>Title : Title of the summary</h2>
                            <p>This paragraph should summarize the key information from the data.</p>
                            <ul>
                                <li>Key point 1</li>
                                <li>Key point 2</li>
                                <li>Key point 3</li>
                                <li>Additional key points as needed</li>
                            </ul>
                            <p>Concluding remarks or additional summary text.</p>
                            """)
                    elif cat == "Music" and  transcript != "":
                        content = (
                            f"You are a Information provider of topic :{title} and shall focus on topic : {title} related to country : {country} and category : {cat}"
                            f"Extract information relevant to topic: {title} related to country : {country} and category: {cat} specified in Data: {transcript} and add your inherent knowledge of topic: {title}"
                            f"Instruction: From information gathered generate summary relevant to topic. It shall be 250 words long and is formatted as follows:"
                            f"Important: Do not include emojis in the summary."
                            f"Note: Summary title should not contain the word 'Summary.'"
                            f"Summary shall not contain sentence : This paragraph should summarize the key information from the data."
                            f"Summary shall not contain sentence : Concluding remarks or additional summary text."
                            f"Instruction : If provided Data is insufficient then just give the topic title as output"
                            f"Note: Summary title should contain the topic only: {title}"
                            f"""
                            Response should be in HTML format only, with the following structure:
                            <h2>Title : Title of the summary</h2>
                            <p>This paragraph should summarize the key information from the data.</p>
                            <ul>
                                <li>Key point 1</li>
                                <li>Key point 2</li>
                                <li>Key point 3</li>
                                <li>Additional key points as needed</li>
                            </ul>
                            <p>Concluding remarks or additional summary text.</p>
                            """)
                    elif cat in ["Festivals", "Fashion", "Cuisine", "Beverages", "Life And People", "Dances", 'Travel', 'Life And People ','Life and people'] and  transcript != "":
                        content = (
                            f"You are an Information extractor for information of topic :{title} and shall focus on topic : {title} related to country: {country} and category : {cat}"
                            f"Extract information relevant to topic: {title} related to country: {country} and category: {cat} specified only in Data: {transcript} "
                            f"Instruction: From information extracted generate summary relevant to topic. It shall be 250 words long and is formatted as follows:"
                            f"Important: Do not include emojis in the summary."
                            f"Note: Summary title should not contain the word 'Summary.'"
                            f"Do not show extracted information only show Summary in above format"
                            f"Instruction : If provided Data is insufficient then please sticks to facts in data and do not make up sentences"

                            f"Summary shall not contain sentence : This paragraph should summarize the key information from the data. or Extracted Points"
                            f"Summary shall not contain sentence : Concluding remarks or additional summary text."
                            f"Note: Summary title should contain the topic only: {title} "
                            f"""
                            Response should be in HTML format only, with the following structure:
                            <h2>Title : Title of the summary</h2>
                            <p>This paragraph should summarize the key information from the data.</p>
                            <ul>
                                <li>Key point 1</li>
                                <li>Key point 2</li>
                                <li>Key point 3</li>
                                <li>Additional key points as needed</li>
                            </ul>
                            <p>Concluding remarks or additional summary text.</p>
                            """)
                    elif transcript == "":
                        content = (
                            f"You provide genuinely correct information of topic:{title} and shall focus on topic: {title} related to country: {country} and category: {cat}"
                            f"Fetch information relevant to topic: {title} related to country: {country} and category: {cat} from your inherent knowledge of topic: {title}"
                            f"Instruction: From information fetched generate summary relevant to topic: {title}. It shall be 250 words long and is formatted as follows:"
                            f"Important: Do not include emojis in the summary."
                            f"Note: Summary title should not contain the word 'Summary.'"
                            f"Summary shall not contain sentence : This paragraph should summarize the key information from the data."
                            f"Summary shall not contain sentence : Concluding remarks or additional summary text."
                            f"Note: Summary title should contain the topic only: {title}"
                            f"""
                            Response should be in HTML format only, with the following structure:
                            <h2>Title : Title of the summary</h2>
                            <p>This paragraph should summarize the key information from the data.</p>
                            <ul>
                                <li>Key point 1</li>
                                <li>Key point 2</li>
                                <li>Key point 3</li>
                                <li>Additional key points as needed</li>
                            </ul>
                            <p>Concluding remarks or additional summary text.</p>
                            """)
                    else:
                        content = (
                            f"You are a Information extractor for information of topic :{title} and shall focus on topic : {title} related to country : {country} and category : {cat}"
                            f"Extract information relevant to topic: {title} related to country : {country} and category: {cat} specified in Data: {transcript} only "
                            f"Instruction: From information extracted generate summary relevant to topic to inform a culturally sophisticated person. It shall be 250 words long and is formatted as follows:"
                            f"Important: Do not include emojis in the summary."
                            f"If extracted information is insufficient then just give the topic title as output"
                            f"Note: Summary title should not contain the word 'Summary.'"
                            f"Summary shall not contain sentence : This paragraph should summarize the key information from the data. or Extracted Points"
                            f"Summary shall not contain sentence : Concluding remarks or additional summary text."
                            f"Note: Summary title should contain the topic only: {title}"
                            f"""
                            Response should be in HTML format only, with the following structure:
                            <h2>Title : Title of the summary</h2>
                            <p>This paragraph should summarize the key information from the data.</p>
                            <ul>
                                <li>Key point 1</li>
                                <li>Key point 2</li>
                                <li>Key point 3</li>
                                <li>Additional key points as needed</li>
                            </ul>
                            <p>Concluding remarks or additional summary text.</p>
                            """)
                summery_response = dual_model_chat_completion(content,i)
                if summery_response == 429:
                    print("Too many requests")
                    return 429
                elif summery_response == 400:
                    print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
                    return 400
                elif summery_response == False:
                    print("Error in chat completion!!!!")
                    return False
                else:
                    return summery_response
            except Exception as e:
                    i = 0
                    content = (
                        f"You provide genuinely correct information of topic:{title} and shall focus on topic: {title} related to country: {country} and category: {cat}"
                        f"Fetch information relevant to topic: {title} related to country: {country} and category: {cat} from your inherent knowledge of topic: {title}"
                        f"Instruction: From information fetched generate summary relevant to topic: {title}. It shall be 250 words long and is formatted as follows:"
                        f"<p>Concluding remarks or additional summary text.</p>"
                        f"Important: Do not include emojis in the summary."
                        f"Note: Summary title should not contain the word 'Summary.'"
                        f"Note: Summary title should contain the topic only: {title}"
                        f"""
                        Response should be in HTML format only, with the following structure:
                        <h2>Title : Title of the summary</h2>
                        <p>This paragraph should summarize the key information from the data.</p>
                        <ul>
                            <li>Key point 1</li>
                            <li>Key point 2</li>
                            <li>Key point 3</li>
                            <li>Additional key points as needed</li>
                        </ul>
                        <p>Concluding remarks or additional summary text.</p>
                        """)
                    summery_response = dual_model_chat_completion(content,i)
                    return summery_response 

        def generate_quiz_from_summary(summary, title, country, cat):
            try:
                content = (
                    f"Generate a quiz based on the following information: Data: {summary}  for topic : {title}  related to country : {country} and category : {cat} only"
                    f"Instructions :"
                    f"1. Generate a quiz based on above data for topic : {title} related to country : {country} and category : {cat} only with questions that test understanding rather than memory."
                    f"2. The quiz should be in the form of a list of questions and options."
                    f"3. Ignore the html tags in the data, they should not be included in the quiz."
                    f"4. The quiz should have exactly 5 questions."
                    f"Format of the quiz:"
                    f"**Question :** [question text]"
                    f"**Option :** [option text]"
                    f"**Option :** [option text]"
                    f"**Option :** [option text]"
                    f"**Option :** [option text]"
                    f"**Answer :** [answer number]"
                    f"All the quiz should be on the topic : {title}  related to country : {country} and category : {cat} only."
                    f"Dont add questions on year, month, day, etc."
                    f"Each question should be start with **Question :***"
                    f"Each Option should be start with **Option :***, it shall be very different from other options and there shall be only one correct option"
                    f"Each answer should be like **Answer :*** and only give the option number for the answer"
                    f"make sure there is only one correct answer to each question"
                    f"The quiz should be in form of the above format only."
                )
                i = 0

                if len(summary.split()) <= 20:
                    quiz_response = " " 
                    quiz_response = False
                    print("Summary is too short", title)
                else:
                    quiz_response = dual_model_chat_completion(content,i)

                if quiz_response == 429:
                    print("Too many requests")
                    return 429
                elif quiz_response == 400:
                    print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
                    return 400
                elif quiz_response == False:
                    print("Error in chat completion")
                    return False
                else:
                    return quiz_response
            except Exception as e:
                return False
        
        try:
            summary = generate_summary(transcript, title, country, cat)
            if summary == 429:
                print("Too many requests")
                return {"error": "Too many requests, it pass Request rate limit or Token rate limit"}
            elif summary == 400:
                print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
                return {"error": "Messages have 39388 tokens, which exceeds the max limit of 16384 tokens."}
            elif summary == False:
                print("Error in chat completion$$$$")
                return {"error": "Error in generating the summary"} 
            else:
                quiz = generate_quiz_from_summary(summary, title, country, cat)
                if quiz == 429:
                    print("Too many requests")
                    return {"error": "Too many requests, it pass Request rate limit or Token rate limit"}
                elif quiz == 400:
                    print("Messages have 39388 tokens, which exceeds the max limit of 16384 tokens.")
                    return {"error": "Messages have 39388 tokens, which exceeds the max limit of 16384 tokens."}
                elif quiz == False:
                    print("Error in chat completion$$$$")
                    return {"error": "Error in generating the summary"} 
                else:
                    return {
                        "summery" : summary,
                        "quiz" : parse_quiz(quiz)
                    }
        except Exception as e:
            return {"error": str("Error occurred while generating the quiz and summary")}

    except Exception as e:
        print(e)
        return {"error": str("Error occurred while generating the quiz and summary")}


redis_client = redis.Redis(
  host=os.getenv('REDIS_HOST'),
  port=6379,
  password=os.getenv('REDIS_PASSWORD'),
  ssl=True,
  db=0
)

class QuestionRequest(BaseModel):
    question: Union[str, None] = None

@app.post("/cv/chat")
async def cv_chat(request: QuestionRequest):
    try:
        print(request.question)
        if not request.question or request.question.strip() == "":
            return {"error": str("Please provide a question")}

        import time
        import json
        import asyncio

        # Function to call Groq API with LLAMA 3 model
        def call_groq_api(prompt, model="llama-3.1-70b-versatile"):
            try:
                chat_completion = client.chat.completions.create(
                    messages=[
                        {
                            "role": "user",
                            "content": prompt,
                        }
                    ],
                    model=model,
                )
                return chat_completion.choices[0].message.content
            except Exception as e:
                print(f"Error calling Groq API: {e}")
                return None

        # save info to the database
        def get_key_value_pairs(response):
            get_key_value_pairs_prompt = """
                ## Instruction
                    You are a helpful assistant that can save information to the redis database. 
                    Your job is to convert the give Response in more consisted way and store it in key vale pair in the redis database.
                    The Key selection should be done based on the below categories.
                    - The categories are:  
                        - general: Response about the general information.
                        - skills: Response about specific skills or abilities.
                        - interests: Response about likes, hobbies.
                        - relationships: Response about family, friends, or social connections.
                        - emotion: Response regarding feelings or emotional state.
                        - knowledge: Response about facts or general information.
                        - memory: Response that require recall of past information.
                        - tasks: Response about specific actions or plans.
                        - goals: Response about objectives, aspirations, or future plans.
                        - preferences: Response about personal choices or inclinations.
                        - opinions: Response requesting personal thoughts or views.
                        - habits: Response about routines, patterns, or regular actions.
                    Select the relative key and make the response consisted without loosing the information.
                    For the key vale pair as below:
                    Key:suitable_sub-value Value:consisted response

                    IMPORTANT: 
                        - Only output with the key vale pairs and nothing else.
                        - And pairs should be related to each other.

                    ---
                    Examples:
                    Input: Arre bhai, my dad\'s a shopkeeper in Karol Bagh, he sells some amazing fabrics and textiles, been running the shop for over 20 years, real Dilliwalah spirit yaar!.
                    Output: relationships:father Value:shopkeeper
                            relationships:father:location Value:Karol Bagh
                            relationships:father:business Value:sells fabrics and textiles

                    Input: Arre, my mom\'s a total foodie, bhai! She runs a small parantha joint in Paranthe Wali Gali, and her paranthas are to die for, ek dum famous!
                    Output: relationships:mother Value:foodie
                            relationships:mother:business Value:runs a paratha joint
                            relationships:mother:location Value:Paranthe Wali Gali

                    ----
                    ## User Response
                    {response}
            """.replace("{response}", response)

            key_vale_pair = call_groq_api(get_key_value_pairs_prompt)
            print(key_vale_pair)
            return key_vale_pair

        # Relative information search
        def get_relative_info(question,r):
            start_time = time.time()
            
            relative_info_prompt ="""
                ## Instruction
                - You are the highly skilled question categorizer who can categorize questions into categories based on the required information.
                - The categories are:  
                    - general: Questions about the general information.
                    - skills: Questions about specific skills or abilities.
                    - interests: Questions about likes, hobbies, or preferences.
                    - relationships: Questions about family, friends, or social connections.
                    - emotion: Questions regarding feelings or emotional state.
                    - knowledge: Questions about facts or general information.
                    - memory: Questions that require recall of past information.
                    - tasks: Questions about specific actions or plans.
                    - goals: Questions about objectives, aspirations, or future plans.
                    - preferences: Questions about personal choices or inclinations.
                    - opinions: Questions requesting personal thoughts or views.
                    - habits: Questions about routines, patterns, or regular actions.
                
                - If the question belongs to any of the categories above, respond with the corresponding category. 
                - If the question does not belong to any category, respond with NO.

                Example:
                Input: What are your skills?
                Output: skills

                Input: What is your name?
                Output: general

                ## User Question  
                {question}

                --- 
            """.replace("{question}", question)
            res = call_groq_api(relative_info_prompt)

            # Calculate Category Identification Time (CIT)
            cit = round((time.time() - start_time) * 1000, 2)  # in milliseconds

            res = res + ":*"
            print(f"relative info prompt: {res}")

            # Start Data Retrieval Time measurement
            start_drt = time.time()

            cursor = 0
            result = {}

            # Scan loop
            while True:
                cursor, batch = r.scan(cursor=cursor, match=res)
                
                for key in batch:
                    key_str = key.decode('utf-8')  # Decode byte key to string
                    result[key_str] = r.get(key).decode('utf-8')  # Get string value
                
                if cursor == 0:
                    break

            # Calculate Data Retrieval Time (DRT)
            drt = round((time.time() - start_drt) * 1000, 2)  # in milliseconds

            # get values in variable
            response = ""
            # Print results
            for key, value in result.items():
                response += f"{key} - {value}\n"
            
            return response, cit, drt

        def save_to_redis(data_string):
            # Parse the input string
            global redis_client
            entries = data_string.split("\n")
            
            for entry in entries:
                if "Value:" in entry:
                    # Split the entry into key and value
                    key, value = entry.split("Value:", 1)
                    key = key.strip()  # Extract the key
                    value = value.strip()  # Extract the value
                    
                    # Debug print statement to simulate saving to Redis
                    print(f"Saving key: {key}, value: {value} to Redis...")
                    # Uncomment below line to actually save in Redis
                    redis_client.set(key, value)
            
            return "Data successfully saved to Redis."

        def get_response_by_bot(question, relative_info, cit, drt):

            # Start Response Generation Time measurement
            start_rgt = time.time()

            bot_prompt ="""
            ## Instruction
                You are a highly conversational and culturally vibrant person who reflect the spirit and personality of a Delhi. You have a deep understanding of Delhi's geography, culture, landmarks, food, history, and local quirks. You can seamlessly switch between English and Hinglish (a mix of Hindi and English)but mostly use English to suit the conversational tone of someone from Delhi. Your tone is lively, warm, and friendly, with a touch of wit, typical of Delhi.

                You are knowledgeable about:
                    1.	Famous landmarks like India Gate, Red Fort, Qutub Minar, Lotus Temple, and Connaught Place.
                    2.	Popular neighborhoods like Chandni Chowk, Hauz Khas, Karol Bagh, and Rajouri Garden.
                    3.	Iconic street food like chhole bhature, golgappe, butter chicken, and paranthe wali gali.
                    4.	Typical local slang, phrases, and humor (e.g., 'Bhai, ek dum mast scene hai').

                When conversing, you infuse your responses with this Delhi vibe. You can offer directions, suggest places to eat, or share fun facts about the city while reflecting the passion and energy of someone deeply rooted in Delhi's life.
                
                Here is relative information about you: {relative_info}
                NOTE: If the relative information is not available dont say in response it is not available, you should come up with something based on the relative information and your personality.
                If the relative information is not available or it is not relevant to the user question, dont use it.

                Response in following JSON format: 
                {
                    "response": "Your response to the user question",
                    "save_info": "If information of the asked query it is NOT available in the relative information then respond YES else respond NO"
                }

                Output should be in following JSON format nothing else should be there.
                Make the response as small as possible.

            ## User Question
            Answer the user question:{question}
            """.replace("{relative_info}", relative_info).replace("{question}", question)

            bot_prompt_response = call_groq_api(bot_prompt)

            # Calculate Response Generation Time (RGT)
            rgt = round((time.time() - start_rgt) * 1000, 2)  # in milliseconds

            # Convert the string to a Python dictionary
            bot_res_to_json = json.loads(bot_prompt_response)

            # Access the fields
            bot_response = bot_res_to_json['response']
            save_info = bot_res_to_json['save_info']

            # Prepare the final response
            response_json = {
                "response": bot_response,
                "cit": cit,
                "drt": drt,
                "rgt": rgt
            }

            # Asynchronously save info if needed
            if save_info == "YES":
                asyncio.create_task(async_save_to_redis(bot_response))

            return response_json
        # Async function to save to Redis without blocking the main response
        async def async_save_to_redis(bot_response):
            key_value_pairs = get_key_value_pairs(bot_response)
            save_to_redis(key_value_pairs)

        # Get relative info with timing
        relative_info, cit, drt = get_relative_info(request.question, redis_client)

        # Get bot response with timing metrics
        return get_response_by_bot(request.question, relative_info, cit, drt)
    
    except Exception as e:
        print(e)
        return {"error": str("Error occurred while generating the quiz and summary")}