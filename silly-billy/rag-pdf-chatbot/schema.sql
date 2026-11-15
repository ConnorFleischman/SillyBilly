CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
    document_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    filename TEXT,
    file_hash TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS documents_file_hash_unique
ON documents (file_hash);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(document_id),
    page_number INTEGER,
    text VARCHAR,
    embedding VECTOR(384)
);
