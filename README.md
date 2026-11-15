# SillyBilly
Marist University Hackathon 2026 team SillyBilly's repository. 

Silly Billy helps students find important details in their course syllabi. You can upload a PDF of a syllabus to find course information, assignment deadlines, and other important course-related information; with citations to the original document. 

## Run locally

Use Python 3.10 or later. From the project root, run:

### Windows PowerShell

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r silly-billy/requirements.txt -e ./silly-billy/rag-pdf-chatbot
```

### macOS/Linux

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r silly-billy/requirements.txt -e ./silly-billy/rag-pdf-chatbot
```

## Connect to a Database

Create a PostgreSQL database and user, install pgVector on the server, then apply the schema using:

```sh
psql -h localhost -U YOUR_DB_USER -d YOUR_DB_NAME -f silly-billy/rag-pdf-chatbot/schema.sql
```

## Configure the RAG pipeline

Copy ~/.env.example and set the placeholders for the database and Gemini API key with the proper credentials. Restart the server once the credentials are set.

## Run it

Windows:

```powershell
.\.venv\Scripts\python.exe -m flask --app silly-billy/app.py run
```

macOS/Linux:

```sh
.venv/bin/python -m flask --app silly-billy/app.py run
```

Open http://127.0.0.1:5000.
