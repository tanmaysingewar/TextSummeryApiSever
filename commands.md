## Create the env with uv
uv venv
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
 
## To run the server in background with no log files
nohup uvicorn main:app --host 0.0.0.0 --port 5000 


# Additional Commands
## remove folder and its content
sudo rm -rf <folder>

##  git clone
git clone <url>

## create the file
touch <file>

## write in the file
vim <file>

## Hidden files
ls -la

## show all running processes
ps xw

## kill a process
kill <PID>