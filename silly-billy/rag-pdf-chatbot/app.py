
import tempfile
from pathlib import Path

import streamlit as st

from rag_backend.database import store_pdf
from rag_backend.generation import generate_answer

st.set_page_config(
    page_title="RAG PDF Chatbot",
    page_icon="📄",
    layout="centered"
)

st.title("📄 RAG PDF Chatbot")
st.write("Upload a PDF and ask questions about its contents.")

# Remember the selected document between interactions
if "document_id" not in st.session_state:
    st.session_state.document_id = None

if "filename" not in st.session_state:
    st.session_state.filename = None

# Step 1: Upload a PDF
uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"]
)

if uploaded_file is not None:
    # Process only when the user clicks the button
    if st.button("Process PDF"):
        temporary_path = None

        try:
            with st.spinner("Processing PDF and generating embeddings..."):
                # Save uploaded bytes temporarily
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf",
                    delete=False
                ) as temporary_file:
                    temporary_file.write(uploaded_file.getbuffer())
                    temporary_path = Path(temporary_file.name)

                # Use our existing backend
                document_id = store_pdf(temporary_path)

                st.session_state.document_id = document_id
                st.session_state.filename = uploaded_file.name

            st.success("PDF processed successfully!")

        except Exception as error:
            st.error(f"Failed to process PDF: {error}")

        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

# Step 2: Ask questions
if st.session_state.document_id is not None:

    st.info(
        f"Selected PDF: {st.session_state.filename}"
    )

    question = st.text_input(
        "Ask a question about your PDF"
    )

    if st.button("Generate Answer"):

        if not question.strip():
            st.warning("Please enter a question.")

        else:
            try:
                with st.spinner("Searching PDF and generating answer..."):
                    answer = generate_answer(
                        question,
                        st.session_state.document_id
                    )

                st.subheader("Answer")
                st.markdown(answer or "No answer was generated.")

            except Exception as error:
                st.error(f"Failed to generate answer: {error}")
