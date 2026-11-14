from pathlib import Path

import pymupdf
from flask import Flask, jsonify, request

from summarize import SummaryUnavailable, summarize_syllabus

SITE = Path(__file__).resolve().parent / "site"
MAX_PDF_BYTES = 25 * 1024 * 1024

app = Flask(__name__, static_folder=str(SITE), static_url_path="")
# Leave space for multipart headers in addition to the PDF itself.
app.config["MAX_CONTENT_LENGTH"] = MAX_PDF_BYTES + 64 * 1024


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="Choose a PDF no larger than 25 MB."), 413


@app.post("/api/summarize")
def summarize():
    upload = request.files.get("syllabus")
    if not upload or Path(upload.filename).suffix.lower() != ".pdf":
        return jsonify(error="Choose a PDF syllabus."), 400

    pdf_bytes = upload.stream.read(MAX_PDF_BYTES + 1)
    if len(pdf_bytes) > MAX_PDF_BYTES:
        return too_large(None)
    if not pdf_bytes.startswith(b"%PDF-"):
        return jsonify(error="The selected file is not a readable PDF."), 400

    try:
        with pymupdf.open(stream=pdf_bytes, filetype="pdf") as pdf:
            if pdf.needs_pass:
                return jsonify(error="Choose a PDF without password protection."), 422
            text = "\n\n".join(page.get_text(sort=True) for page in pdf)
    except (RuntimeError, ValueError):
        return jsonify(error="The selected file is not a readable PDF."), 400

    if not text.strip():
        return jsonify(error="This PDF has no selectable text. Try a text-based PDF."), 422

    try:
        return jsonify(summarize_syllabus(text))
    except SummaryUnavailable:
        return jsonify(error="PDF text extracted. Summary generation is still being connected. You can view an example below the upload form."), 501
