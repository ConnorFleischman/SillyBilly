import psycopg
from database_config import get_database_url
from chunk import all_chunks
from embeddings import get_embedding
from pgvector.psycopg import register_vector

conn = psycopg.connect(get_database_url())
register_vector(conn)
print("Connected to PostgreSQL")
cur = conn.cursor()
for i, chunks in enumerate(all_chunks):
    page_number = chunks["page"]
    text = chunks["text"]
    embedding = get_embedding(text)
    cur.execute('INSERT INTO chunks(document_id, page_number, text, embedding) VALUES (%s, %s, %s, %s)', (2, page_number, text, embedding))
conn.commit()
conn.close()