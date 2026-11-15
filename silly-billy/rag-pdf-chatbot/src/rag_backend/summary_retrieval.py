"""Bounded, document-scoped evidence for summary generation (no provider calls)."""
from dataclasses import dataclass

import psycopg
from pgvector.psycopg import register_vector

from .database_config import get_database_url
from .embeddings import get_embedding

# Fixed order is part of the interface; no generation or completeness claims.
SECTION_QUESTIONS = {
    "overview": "What is the course title, description, objectives and instructor information?",
    "due_dates": "What assignments, projects and homework are due, and on what deadlines?",
    "lecture_dates": "What are the lecture meeting days, times and dated topic schedule?",
    "exam_dates": "When are the quizzes, midterms and final exams scheduled?",
    "grading": "What are the grading weights, assessment percentages and grade policies?",
}
CANDIDATE_LIMIT = 20
MAX_SECTION_CHARS = 4000
MAX_TOTAL_CHARS = 20000


@dataclass(frozen=True)
class EvidencePassage:
    """Original stored text (possibly prefix-truncated), with its source page."""

    chunk_id: int
    page_number: int
    text: str

    def render(self):
        return f"[Page {self.page_number}] {self.text}"


def _positive_integer(value, name, maximum):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(f"{name} must be an integer between 1 and {maximum}")


def retrieve_summary_evidence(
    document_id, *, section_char_limit=MAX_SECTION_CHARS,
    total_char_limit=MAX_TOTAL_CHARS,
):
    """Return all five keys mapped to ranked lists of EvidencePassage.

    Empty lists mean no usable retrieved evidence, not proof of absent facts.
    Each section searches separately, selecting at most 20 candidates. Exact
    passages repeated with different whitespace/case are collapsed per section;
    a passage relevant to two sections may appear in both. Page tags count in
    budgets. Each section receives an equal share of the total budget (unused
    space is not reassigned), so earlier sections cannot consume later shares.
    Prefix truncation preserves source wording but may omit a trailing fact.
    Errors from embeddings or the database propagate. Nothing loads at import.
    """
    _positive_integer(document_id, "document_id", 2147483647)
    _positive_integer(section_char_limit, "section_char_limit", MAX_SECTION_CHARS)
    _positive_integer(total_char_limit, "total_char_limit", MAX_TOTAL_CHARS)
    budget = min(section_char_limit, total_char_limit // len(SECTION_QUESTIONS))
    result = {section: [] for section in SECTION_QUESTIONS}
    with psycopg.connect(get_database_url()) as conn:
        register_vector(conn)
        with conn.cursor() as cur:
            for section, question in SECTION_QUESTIONS.items():
                embedding = get_embedding(question)
                cur.execute(
                    """
                    SELECT chunk_id, text, page_number
                    FROM chunks
                    WHERE document_id = %s
                    ORDER BY embedding <=> %s, page_number, chunk_id
                    LIMIT %s
                    """,
                    (document_id, embedding, CANDIDATE_LIMIT),
                )
                remaining = budget
                seen = set()
                for chunk_id, text, page in cur.fetchall():
                    if not text or not text.strip() or page is None:
                        continue
                    key = " ".join(text.split()).casefold()
                    if key in seen:
                        continue
                    seen.add(key)
                    available = remaining - len(f"[Page {page}] ")
                    if available <= 0:
                        break
                    excerpt = text[:available]
                    passage = EvidencePassage(chunk_id, page, excerpt)
                    result[section].append(passage)
                    remaining -= len(passage.render())
    return result
