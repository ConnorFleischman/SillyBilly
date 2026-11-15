class SummaryUnavailable(Exception):
    """Raised while the project's summary generator is being integrated."""


def summarize_syllabus(document_id: int) -> dict[str, list[str]]:
    """Generate summary fields from an indexed document ID (pending M3/M4)."""
    raise SummaryUnavailable()
