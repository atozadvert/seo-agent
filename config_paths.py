from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def resolve_project_path(path_value: str | None, default: str | None = None) -> Path:
    """Resolve a path relative to the project root, keeping absolute paths intact."""
    raw_value = path_value or default or ""
    if not raw_value:
        return PROJECT_ROOT
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return PROJECT_ROOT / candidate


def get_db_path() -> str:
    """Return the canonical SQLite database path for this project."""
    if os.getenv("DB_PATH"):
        return str(resolve_project_path(os.getenv("DB_PATH")))
    if os.getenv("RAILWAY_ENVIRONMENT"):
        return "/tmp/seo_guardian.db"
    return str(resolve_project_path("seo_guardian.db"))


def get_token_path() -> str:
    """Return the canonical Google token path for this project."""
    return str(resolve_project_path(os.getenv("TOKEN_FILE") or "token.pickle"))
