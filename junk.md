
@app.post("/quiz")
async def quiz(
    # upload_file: Annotated[UploadFile, File()]):
    userPrompt: Annotated[str, Form()] = None):
    try:
        # file_read = await upload_file.read()
        # file_path = os.path.join(UPLOAD_DIR, upload_file.filename)
        # os.makedirs(UPLOAD_DIR, exist_ok=True)
        # with open(file_path, "wb") as f:
        #     f.write(file_read)

        # if upload_file.filename.endswith(".pdf"):
        #     text = extract_text_from_pdf(file_path)
        # elif upload_file.filename.endswith(".docx"):
        #     text = extract_text_from_docx(file_path)
        # elif upload_file.filename.endswith(".txt"):
        #     text = extract_text_from_txt(file_path)
        # else:
        #     return {"error": "Unsupported file type"}

        dist = YouTubeTranscriptApi.get_transcript(userPrompt)

        formatter = TextFormatter()

        # .format_transcript(transcript) turns the transcript into a JSON string.
        json_formatted = formatter.format_transcript(dist)

        print(json_formatted)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            length_function=len,
            is_separator_regex=False,
        )

        chunk = text_splitter.create_documents([json_formatted])

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

        
        
