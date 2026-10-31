"""Application settings, read from environment variables with safe defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    max_upload_bytes: int
    max_rows: int
    max_columns: int
    session_ttl_seconds: int
    preview_rows: int
    cors_origins: tuple[str, ...]
    # Intelligence layer. Thresholds are defaults; the API lets callers override them.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_threshold: float = 0.85
    fuzzy_threshold: float = 90.0
    similarity_top_k: int = 5
    # Similarity compares every product with every other, so it is capped.
    max_similarity_rows: int = 5000
    # Cap on simultaneous in-memory catalogues; the least recently used is evicted.
    max_sessions: int = 20


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def get_settings() -> Settings:
    origins = os.environ.get(
        "CATALOGUEIQ_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    return Settings(
        max_upload_bytes=_int("CATALOGUEIQ_MAX_UPLOAD_BYTES", 10 * 1024 * 1024),
        max_rows=_int("CATALOGUEIQ_MAX_ROWS", 50_000),
        max_columns=_int("CATALOGUEIQ_MAX_COLUMNS", 100),
        session_ttl_seconds=_int("CATALOGUEIQ_SESSION_TTL_SECONDS", 2 * 60 * 60),
        preview_rows=_int("CATALOGUEIQ_PREVIEW_ROWS", 20),
        cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        embedding_model=os.environ.get(
            "CATALOGUEIQ_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
        semantic_threshold=_float("CATALOGUEIQ_SEMANTIC_THRESHOLD", 0.85),
        fuzzy_threshold=_float("CATALOGUEIQ_FUZZY_THRESHOLD", 90.0),
        similarity_top_k=_int("CATALOGUEIQ_SIMILARITY_TOP_K", 5),
        max_similarity_rows=_int("CATALOGUEIQ_MAX_SIMILARITY_ROWS", 5000),
        max_sessions=_int("CATALOGUEIQ_MAX_SESSIONS", 20),
    )
