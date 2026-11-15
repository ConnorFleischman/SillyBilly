from pathlib import Path

from rag_backend.ingestion import (
    MAX_PDF_BYTES, InvalidPDF, PDFTooLarge, UnprocessablePDF, ingest_pdf,
)
from flask import Flask, jsonify, request

from summarize import summarize_syllabus

SITE = Path(__file__).resolve().parent / "site"

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

    try:
        document_id = ingest_pdf(upload.stream, upload.filename)
    except PDFTooLarge:
        return too_large(None)
    except InvalidPDF as error:
        return jsonify(error=str(error)), 400
    except UnprocessablePDF as error:
        return jsonify(error=str(error)), 422
    except Exception:
        # Driver/config exception text can contain credentials.
        return jsonify(error="PDF ingestion is unavailable. Please try again later."), 503

    try:
        return jsonify(summarize_syllabus(document_id))
    except Exception:
        # Retrieval and unexpected failures may contain credentials or PDF text.
        return jsonify(error="Summary generation is unavailable. Please try again later."), 503
