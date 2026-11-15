import pymupdf


def extract_text(pdf_path):
    """Return selectable text keyed by original 1-based page number.

    Empty pages remain in the mapping so callers never renumber later pages.
    The document is closed even if page extraction fails.
    """
    with pymupdf.open(pdf_path) as doc:
        return {
            page_number: page.get_text()
            for page_number, page in enumerate(doc, start=1)
        }
