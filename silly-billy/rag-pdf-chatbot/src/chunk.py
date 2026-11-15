from python_reader import extract_text


def chunk_text(text, chunk_size=500, overlap=100):
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size must be positive and overlap must be smaller.")

    chunks = []

    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        chunks.append(chunk)

    return chunks


def chunk_pdf(pdf_path):
    pages_text = extract_text(pdf_path)
    all_chunks = []

    for page_number, text in pages_text.items():
        page_chunks = chunk_text(text)

        for chunk in page_chunks:
            all_chunks.append({
                "page": page_number,
                "text": chunk
            })

    return all_chunks