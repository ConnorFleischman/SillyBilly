"""Bounded upload ingestion; HTTP validation and error mapping belong to callers."""
from pathlib import Path
import tempfile
from typing import BinaryIO

from .database import store_pdf

MAX_PDF_BYTES = 25 * 1024 * 1024


def ingest_pdf(source: bytes | BinaryIO, original_filename: str) -> int:
    """Store upload bytes or a binary stream positioned at the PDF's start.

    Read at most 25 MiB + 1 from streams; never close caller-owned streams.
    Require a PDF signature and bounded, nonempty bytes. Full PDF parsing and
    text checks remain in store_pdf; callers own transport validation/error
    mapping. Client names are basename-only display metadata, never disk paths.
    This function owns and removes its temporary directory on every exit,
    including partial writes and storage errors. Return the existing/new ID.
    """
    if not isinstance(original_filename, str):
        raise TypeError("original_filename must be a string")
    filename = original_filename.replace("\\", "/").rsplit("/", 1)[-1]
    if filename in ("", ".", "..") or any(ord(char) < 32 for char in filename):
        raise ValueError("A valid display filename is required")
    data = source if isinstance(source, bytes) else source.read(MAX_PDF_BYTES + 1)
    if not isinstance(data, bytes):
        raise TypeError("PDF input must supply bytes")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the 25 MiB limit")
    if not data.startswith(b"%PDF-"):
        raise ValueError("PDF signature is missing")

    with tempfile.TemporaryDirectory(prefix="silly-billy-upload-") as directory:
        path = Path(directory) / "upload.pdf"
        path.write_bytes(data)
        return store_pdf(path, original_filename=filename)
