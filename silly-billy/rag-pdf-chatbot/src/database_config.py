"""Shared PostgreSQL configuration for the app and examples.

Set DATABASE_URL in the process environment before connecting, for example
postgresql://postgres:password@localhost:5432/rag_chatbot.
Credentials are deployment-specific; there is no hardcoded user or password.
"""

import os
from pathlib import Path


def get_database_url():
    """Read configuration at call time so environment changes take effect."""
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise ValueError(
            "DATABASE_URL is required. Set it to your PostgreSQL connection URL "
            "(postgresql://USER:PASSWORD@HOST:5432/rag_chatbot)."
        )
    return url
