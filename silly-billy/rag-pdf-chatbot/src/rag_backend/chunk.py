from .python_reader import extract_text


def chunk_text(text, chunk_size=500, overlap=100):
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size must be positive and overlap must be smaller.")

    chunks = []

    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        chunks.append(chunk)

    return chunks


def chunk_pages(pages_text, chunk_size=500, overlap=100):
    """Chunk a page-number-to-text mapping without flattening or renumbering.

    Blank pages produce no chunks; nonconsecutive page numbers are preserved.
    """
    all_chunks = []

    for page_number, text in pages_text.items():
        if not text.strip():
            continue
        page_chunks = chunk_text(text, chunk_size, overlap)

        for chunk in page_chunks:
            all_chunks.append({
                "page": page_number,
                "text": chunk
            })

    return all_chunks


def chunk_pdf(pdf_path):
    """Extract and chunk a PDF using the shared page-preserving interfaces."""
    return chunk_pages(extract_text(pdf_path))
