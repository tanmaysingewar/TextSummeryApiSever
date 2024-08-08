## Create the env with uv
uv venv

## Activate the virtual environment:
source .venv/bin/activate

## To install a package into the virtual environment:
uv pip install fastapi
uv pip install -r requirements.txt

## Run Sever
fastapi dev main.py

## Deactivate 
deactivate

## To run the server
uvicorn main:app --host 0.0.0.0 --port 5000 

## To run the server in background with the output logs in file 
nohup uvicorn main:app --host 0.0.0.0 --port 5000  > logs.txt
 
## To run the server in background
nohup uvicorn main:app --host 0.0.0.0 --port 5000 


## YT Likes
https://youtu.be/HCV9nueXQ6Y?feature=shared === error

https://www.youtube.com/watch?v=DHjqpvDnNGE

https://youtu.be/DHjqpvDnNGE?si=49jlB7vXUP9aAonR


# Additional Commands
## Hidden files
ls -la

## show all running processes
ps xw

## kill a process
kill <PID>