"""Local sentence embeddings (all-MiniLM-L6-v2 on CPU).

The model is loaded once, on first use, and reused for every request. The
first load needs internet access to download the model; afterwards the local
Hugging Face cache is used. Embeddings are cached per catalogue session by
text, so re-running with different thresholds, or after a few edits, only
encodes products whose text actually changed.
"""
from __future__ import annotations

import re
import threading
from typing import Callable

import numpy as np

MAX_DESCRIPTION_CHARS = 500
_WS = re.compile(r"\s+")


class EmbeddingModelError(RuntimeError):
    """The embedding model could not be loaded or run."""


def product_text(name: str, category: str = "", brand: str = "", description: str = "") -> str:
    """Build the text to embed. Blank fields are left out, never written as 'None'/'nan'."""
    parts = []
    for label, value in (("", name), ("Category: ", category), ("Brand: ", brand),
                         ("", description[:MAX_DESCRIPTION_CHARS])):
        value = _WS.sub(" ", value or "").strip()
        if value:
            parts.append(f"{label}{value}")
    return ". ".join(parts)


class EmbeddingService:
    def __init__(self, model_name: str, encoder: Callable[[list[str]], np.ndarray] | None = None):
        self.model_name = model_name
        self._encoder = encoder  # injectable for tests
        self._model = None
        self._lock = threading.Lock()

    @property
    def loaded(self) -> bool:
        return self._model is not None or self._encoder is not None

    def _load(self):
        with self._lock:
            if self._model is not None:
                return self._model
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name, device="cpu")
            except Exception as exc:  # network, missing cache, missing package, ...
                raise EmbeddingModelError(
                    f"Could not load embedding model '{self.model_name}': {exc}. "
                    "The first run needs internet access to download the model; after that it "
                    "runs from the local cache. You can still run fuzzy-only matching."
                ) from exc
            return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return L2-normalised float32 embeddings, one row per text."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        try:
            if self._encoder is not None:
                vecs = np.asarray(self._encoder(texts), dtype=np.float32)
            else:
                model = self._load()
                vecs = model.encode(texts, batch_size=32, normalize_embeddings=True,
                                    show_progress_bar=False, convert_to_numpy=True)
        except EmbeddingModelError:
            raise
        except Exception as exc:
            raise EmbeddingModelError(f"Embedding failed: {exc}") from exc
        vecs = np.asarray(vecs, dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.where(norms == 0, 1.0, norms)

    def embed_with_cache(self, texts: list[str], cache: dict[str, np.ndarray]) -> np.ndarray:
        """Embed texts, encoding only those missing from `cache` (which is updated).

        Rows with empty text get an all-zero vector so they never match anything.
        """
        missing = sorted({t for t in texts if t and t not in cache})
        if missing:
            for text, vec in zip(missing, self.encode(missing)):
                cache[text] = vec
        dim = next(iter(cache.values())).shape[0] if cache else 0
        out = np.zeros((len(texts), dim), dtype=np.float32)
        for n, t in enumerate(texts):
            if t:
                out[n] = cache[t]
        return out
