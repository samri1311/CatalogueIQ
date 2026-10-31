"""Shared application singletons (settings and the session store)."""
from __future__ import annotations

from app.config import get_settings
from app.intelligence.embedding_service import EmbeddingService
from app.services.catalogue_store import CatalogueStore

settings = get_settings()
store = CatalogueStore(settings.session_ttl_seconds, settings.max_sessions)
# One shared instance: the model loads once, on first use, not per request.
embedding_service = EmbeddingService(settings.embedding_model)


def get_embedder() -> EmbeddingService:
    return embedding_service
