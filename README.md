# SillyBilly
Marist University Hackathon 2026 team SillyBilly's repository. 

# Silly Billy

Silly Billy helps students find the key details in a course syllabus. Open
`site/index.html` in your browser and choose **View an example** to try the
interface with sample data.

## Run locally

Use Python 3.10 or later. From the project folder on Windows, run:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run
```

On macOS or Linux, use `python3 -m venv .venv` and
`.venv/bin/python` in the last two commands. Open http://127.0.0.1:5000.

The upload endpoint accepts text-based PDFs up to 25 MB. It extracts text
using PyMuPDF and passes that text to `summarize_syllabus()`. Until that
function is wired up, valid uploads show a message confirming PDF extraction.

## Connect the team's RAG pipeline

Replace the placeholder in `summarize.py` with calls to the team's existing
chunking, embedding, PostgreSQL/pgvector storage, and retrieval modules.
Keep each retrieval query scoped to the uploaded syllabus. Retrieve evidence
for each summary section so a single Top-5 search does not have to cover the
whole syllabus. Pass the retrieved excerpts to the LLM and ask it to include
only details supported by those excerpts. If the team wants to use its existing
PDF reader, swap it in at the extraction step in `app.py`.

Return this JSON shape. Each field is a list of strings. Use an empty list
when the syllabus does not give details for a section.

```json
{
  "overview": ["Introduction to Environmental Science"],
  "due_dates": ["Lab report due September 28"],
  "lecture_dates": ["Mondays and Wednesdays, 10:00–11:15 a.m."],
  "exam_dates": ["Midterm on October 14"],
  "grading": ["Labs 25%"]
}
```

## Add to GitHub

Copy the contents of this folder into your repository and commit them on a
branch. Keep API keys and database credentials in server-side environment
variables. GitHub can store all of the source. GitHub Pages can display the
contents of `site/`, and PDF uploads require the Python server.
