from embeddings import get_embedding
import psycopg
from pgvector.psycopg import register_vector

def retrieve_chunks(question):
    question_embedding = get_embedding(question)

    conn = psycopg.connect(
        dbname="rag_chatbot",
        user="meher",
        host="localhost",
        port=5432
    )

    register_vector(conn)
    cur = conn.cursor()

    cur.execute(
    """
    SELECT text, page_number
    FROM chunks
    WHERE document_id = %s
    ORDER BY embedding <=> %s
    LIMIT 5
    """,
    (2, question_embedding)
)

    results = cur.fetchall()
    conn.close()

    return results


if __name__ == "__main__":
    question = "What are the different ways to deal with conflict?"
    results = retrieve_chunks(question)

    for text, page_number in results:
        print(f"Page {page_number}: {text[:200]}")