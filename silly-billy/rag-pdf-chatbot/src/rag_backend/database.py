from pathlib import Path
import hashlib

import psycopg
from .database_config import get_database_url
from pgvector.psycopg import register_vector

from .chunk import chunk_pdf
from .embeddings import get_embedding


def calculate_file_hash(pdf_path):
    hasher = hashlib.sha256()

    with open(pdf_path, "rb") as file:
        for block in iter(lambda: file.read(8192), b""):
            hasher.update(block)

    return hasher.hexdigest()


def store_pdf(pdf_path):
    pdf_path = Path(pdf_path)

    # Step 1: Calculate the PDF fingerprint
    file_hash = calculate_file_hash(pdf_path)

    # Step 2: Connect to PostgreSQL
    with psycopg.connect(get_database_url()) as conn:

        register_vector(conn)

        with conn.cursor() as cur:

            # Step 3: Check if the PDF already exists
            cur.execute(
                """
                SELECT document_id
                FROM documents
                WHERE file_hash = %s
                """,
                (file_hash,)
            )

            existing_document = cur.fetchone()

            if existing_document:
                print("PDF already exists in database.")
                return existing_document[0]

            # Step 4: Extract and chunk the new PDF
            all_chunks = chunk_pdf(pdf_path)

            if not all_chunks:
                raise ValueError("No text extracted from PDF.")

            # Step 5: Register the new PDF
            cur.execute(
                """
                INSERT INTO documents (filename, file_hash)
                VALUES (%s, %s)
                RETURNING document_id
                """,
                (pdf_path.name, file_hash)
            )

            document_id = cur.fetchone()[0]

            # Step 6: Generate embeddings and store chunks
            for chunk in all_chunks:
                embedding = get_embedding(chunk["text"])

                cur.execute(
                    """
                    INSERT INTO chunks
                    (document_id, page_number, text, embedding)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        document_id,
                        chunk["page"],
                        chunk["text"],
                        embedding
                    )
                )

    return document_id