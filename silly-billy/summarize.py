from rag_backend.summary_generation import generate_syllabus_summary


def summarize_syllabus(document_id: int) -> dict[str, list[str]]:
    """Return validated summary fields for the server-indexed document."""
    return generate_syllabus_summary(document_id)
