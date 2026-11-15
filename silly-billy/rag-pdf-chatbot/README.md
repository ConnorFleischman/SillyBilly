# RAG PDF Chatbot

A Retrieval-Augmented Generation (RAG) chatbot that allows users to upload PDF documents and ask questions about their contents.

## Features
- PDF text extraction using PyMuPDF
- Text chunking with overlap
- Local embeddings using all-MiniLM-L6-v2
- PostgreSQL and pgvector for vector storage
- Cosine similarity search
- Gemini API for answer generation
- Streamlit user interface

## Requirements
- Python 3.13
- PostgreSQL with pgvector installed
- Gemini API key

## Installation

From the rag-pdf-chatbot directory:

1. Create a virtual environment:

   python3 -m venv .venv

2. Activate it:

   source .venv/bin/activate

3. Install dependencies:

   pip install -r requirements.txt

## Database Setup

Create a PostgreSQL database named rag_chatbot:

   createdb rag_chatbot

Run the schema:

   psql -d rag_chatbot -f schema.sql

Note: The pgvector PostgreSQL extension must already be installed.

The current Python database configuration uses:
- Database: rag_chatbot
- Username: meher
- Host: localhost
- Port: 5432

Update the PostgreSQL username in src/database.py and src/retrieval.py to match your local setup.

## Gemini API Key

Create a .env file in the rag-pdf-chatbot directory containing:

   GEMINI_API_KEY=your_own_api_key

Never commit your .env file or share your API key.

## Run the Chatbot

From the rag-pdf-chatbot directory:

   streamlit run app.py

Open the local URL shown in the terminal.

Upload a PDF, click Process PDF, enter a question, and click Generate Answer.

## Current Limitations

- PostgreSQL must be configured locally.
- Database connection settings are currently hardcoded.
- The Streamlit interface works locally.
- FastAPI endpoints for integration with the team's frontend have not been implemented yet.
- Scanned PDFs without selectable text may require OCR.

## Future Integration

The RAG backend can be connected to the team's frontend through API endpoints for PDF uploads and question answering.
