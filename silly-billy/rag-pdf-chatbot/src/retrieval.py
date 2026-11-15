import psycopg
from pgvector.psycopg import register_vector
from embeddings import get_embedding


def retrieve_chunks(question, document_id):
    # Step 1: Convert the question into an embedding
    question_embedding = get_embedding(question)

    # Step 2: Connect to PostgreSQL
    with psycopg.connect(
        dbname="rag_chatbot",
        user="meher",
        host="localhost",
        port=5432
    ) as conn:
        register_vector(conn)

        with conn.cursor() as cur:
            # Step 3: Retrieve the 5 most similar chunks
            # belonging to the selected document
            cur.execute(
                """
                SELECT text, page_number
                FROM chunks
                WHERE document_id = %s
                ORDER BY embedding <=> %s
                LIMIT 5
                """,
                (document_id, question_embedding)
            )

            results = cur.fetchall()

    return results


if __name__ == "__main__":
    question = "What are the different ways to deal with conflict?"
    results = retrieve_chunks(question, document_id=2)

    for text, page_number in results:
        print(f"Page {page_number}: {text[:200]}")