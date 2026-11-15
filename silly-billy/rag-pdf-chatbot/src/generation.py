import os
from pathlib import Path

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


def get_gemini_config():
    """Load the existing dotenv locations and read configuration at call time."""
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is required. Set it in the environment or in "
            "src/.env or the project .env file."
        )
    model = os.environ.get("GEMINI_MODEL", DEFAULT_GEMINI_MODEL).strip()
    if not model:
        raise ValueError("GEMINI_MODEL must be nonblank when set. Unset it to use the default model.")
    return api_key, model


def generate_answer(question, document_id):
    # Defer embedding/model dependencies until a question is actually asked.
    from retrieval import retrieve_chunks

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
    api_key, model = get_gemini_config()
    from google import genai

    # Provider exceptions can contain request details; expose only safe guidance.
    try:
        with genai.Client(api_key=api_key) as client:
            response = client.models.generate_content(model=model, contents=prompt)
            return response.text
    except Exception:
        raise RuntimeError(
            "Gemini generation failed. Check GEMINI_API_KEY, GEMINI_MODEL, "
            "network access, and provider availability."
        ) from None



if __name__ == "__main__":
    question = "What are the five ways to deal with conflict?"
    answer = generate_answer(question, document_id=2)
    print(answer)