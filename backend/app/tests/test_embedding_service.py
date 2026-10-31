import sys
import types

import numpy as np
import pytest

from app.intelligence.embedding_service import (
    EmbeddingModelError, EmbeddingService, product_text,
)
from app.tests.fakes import bow_encoder


def test_product_text_skips_blank_fields_and_never_writes_none():
    t = product_text("Blue Mug", category="  ", brand="", description="Holds  coffee")
    assert t == "Blue Mug. Holds coffee"
    assert "None" not in t and "nan" not in t.lower()
    assert product_text("Mug", "Kitchen", "Acme", "") == "Mug. Category: Kitchen. Brand: Acme"
    assert product_text("", "", "", "") == ""


def test_long_description_is_truncated():
    assert len(product_text("A", description="x" * 5000)) < 600


def test_embeddings_are_normalised():
    svc = EmbeddingService("fake", encoder=bow_encoder)
    v = svc.encode(["red shoes", "blue shoes"])
    assert v.dtype == np.float32
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-5)


def test_cache_encodes_only_new_texts_and_zeroes_empty():
    calls = []

    def enc(texts):
        calls.append(list(texts))
        return bow_encoder(texts)

    svc = EmbeddingService("fake", encoder=enc)
    cache: dict = {}
    out = svc.embed_with_cache(["a b", "", "a b", "c d"], cache)
    assert calls == [["a b", "c d"]]  # deduplicated, empty text skipped
    assert not out[1].any() and out[0].any() and np.array_equal(out[0], out[2])

    svc.embed_with_cache(["a b", "c d", "e f"], cache)
    assert calls[1] == ["e f"]  # reused from the session cache


def test_model_loads_once(monkeypatch):
    built = []

    class FakeST:
        def __init__(self, name, device=None):
            built.append((name, device))

        def encode(self, texts, **kw):
            return bow_encoder(texts)

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        types.SimpleNamespace(SentenceTransformer=FakeST))
    svc = EmbeddingService("m")
    svc.encode(["x"])
    svc.encode(["y"])
    assert built == [("m", "cpu")]


def test_load_failure_gives_helpful_error(monkeypatch):
    class Boom:
        def __init__(self, *a, **k):
            raise OSError("no network")

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        types.SimpleNamespace(SentenceTransformer=Boom))
    with pytest.raises(EmbeddingModelError, match="internet access"):
        EmbeddingService("m").encode(["x"])
