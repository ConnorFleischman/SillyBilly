import pymupdf


def extract_text(pdf_path):
    doc = pymupdf.open(pdf_path)
    pages_text = {}

    for page_number, page in enumerate(doc, start=1):
        pages_text[page_number] = page.get_text()

    doc.close()
    return pages_text