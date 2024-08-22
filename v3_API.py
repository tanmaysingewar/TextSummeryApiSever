from fastapi import FastAPI,File,UploadFile,Form
from pydantic import BaseModel

import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import re

from chat_completion import chat_completion

import requests
import json

from ytTranscript import get_yt_transcript

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