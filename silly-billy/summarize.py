class SummaryUnavailable(Exception):
    """Raised while the project's summary generator is being integrated."""


def summarize_syllabus(text: str) -> dict[str, list[str]]:
    """Return overview, due_dates, lecture_dates, exam_dates, and grading."""
    raise SummaryUnavailable()
