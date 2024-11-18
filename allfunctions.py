from groq import Groq

# Initialize the Groq client
client = Groq(
    api_key="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"  # Replace with your actual API key
)

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

    res = res + ":*"
    print(f"relative info prompt: {res}")

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

    # get values in variable
    response = ""
    # Print results
    for key, value in result.items():
        response += f"{key} - {value}\n"
    return response
        
__all__ = ['call_groq_api','get_relative_info','get_key_value_pairs',]