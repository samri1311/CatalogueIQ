"""Test helpers: a deterministic fake encoder so tests need no model download."""
from __future__ import annotations

import re
import zlib

import numpy as np

DIM = 256


def bow_encoder(texts: list[str]) -> np.ndarray:
    """Hashed bag-of-words vectors. Similar wording -> high cosine similarity."""
    out = np.zeros((len(texts), DIM), dtype=np.float32)
    for n, t in enumerate(texts):
        for tok in re.findall(r"[a-z0-9]+", t.lower()):
            out[n, zlib.crc32(tok.encode()) % DIM] += 1.0
    return out
