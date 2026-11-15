import os
from pathlib import Path

from google import genai
from dotenv import load_dotenv
from retrieval import retrieve_chunks

# Load the API key
load_dotenv(Path(__file__).resolve().parent / ".env")
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY was not found in your .env file")

client = genai.Client(api_key=api_key)


def generate_answer(question, document_id):
    # Step 1: Retrieve chunks from the selected PDF
    chunks = retrieve_chunks(question, document_id)

    if not chunks:
        return "No relevant PDF content was found for this document."

    # Step 2: Combine retrieved chunks into context
    context = ""

    for text, page_number in chunks:
        context += f"Page {page_number}: {text}\n\n"

    # Step 3: Create the prompt
    prompt = f"""
    Answer the user's question using only the PDF context below.
    If the answer is not in the context, say you don't know.
    Include relevant page numbers in your answer.

    Context:
    {context}

    Question:
    {question}
    """

    # Step 4: Send the prompt to Gemini
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return response.text


if __name__ == "__main__":
    question = "What are the five ways to deal with conflict?"
    answer = generate_answer(question, document_id=2)
    print(answer)