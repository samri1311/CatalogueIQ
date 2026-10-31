"""In-memory catalogue sessions.

The store is the only place that holds uploaded data. The original DataFrame
is kept separate from the working copy and is never mutated. Everything lives
in process memory and expires after a TTL, so nothing is persisted by default.
Swap this class for a database-backed one later without touching the API.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.models.issue import Issue, IssueStatus, ReviewAction
from app.models.similarity import CandidateStatus


@dataclass
class Catalogue:
    catalogue_id: str
    filename: str
    original: pd.DataFrame
    working: pd.DataFrame
    mapping: dict[str, str] = field(default_factory=dict)
    issues: list[Issue] = field(default_factory=list)
    analyzed: bool = False
    # issue_id -> stack of pre-action snapshots, used by undo
    history: dict[str, list["Snapshot"]] = field(default_factory=dict)
    # (row, column) -> issue_ids whose accepted/edited change is applied, newest last
    cell_stack: dict[tuple[int, str], list[str]] = field(default_factory=dict)
    # Similarity (in memory only): text -> embedding, user decisions per candidate pair,
    # and the count from the most recent run (None until similarity has been run).
    embeddings: dict[str, np.ndarray] = field(default_factory=dict)
    candidate_reviews: dict[str, CandidateStatus] = field(default_factory=dict)
    known_candidates: set[str] = field(default_factory=set)
    potential_duplicates: int | None = None
    last_access: float = field(default_factory=time.perf_counter)

    def reset_review_state(self) -> None:
        """Discard the ledger and restore the working copy to the original upload."""
        self.working = self.original.copy(deep=True)
        self.issues = []
        self.history = {}
        self.cell_stack = {}


@dataclass
class Snapshot:
    status: IssueStatus
    review_action: ReviewAction | None
    revalidation_passed: bool | None
    prev_value: str
    changed_value: bool


class CatalogueStore:
    def __init__(self, ttl_seconds: int, max_sessions: int = 20):
        self._ttl = ttl_seconds
        self._max = max_sessions
        self._items: dict[str, Catalogue] = {}
        self._lock = threading.Lock()

    def create(self, filename: str, df: pd.DataFrame, mapping: dict[str, str]) -> Catalogue:
        self.purge_expired()
        cat = Catalogue(
            catalogue_id=uuid.uuid4().hex,
            filename=filename,
            original=df,
            working=df.copy(deep=True),
            mapping=mapping,
        )
        with self._lock:
            while len(self._items) >= self._max:  # bound memory: evict least recently used
                oldest = min(self._items.values(), key=lambda c: c.last_access)
                del self._items[oldest.catalogue_id]
            self._items[cat.catalogue_id] = cat
        return cat

    def get(self, catalogue_id: str) -> Catalogue | None:
        self.purge_expired()
        with self._lock:
            cat = self._items.get(catalogue_id)
            if cat:
                cat.last_access = time.perf_counter()
            return cat

    def find_by_issue(self, issue_id: str) -> Catalogue | None:
        self.purge_expired()
        with self._lock:
            for cat in self._items.values():
                if any(i.issue_id == issue_id for i in cat.issues):
                    cat.last_access = time.perf_counter()
                    return cat
        return None

    def delete(self, catalogue_id: str) -> bool:
        with self._lock:
            return self._items.pop(catalogue_id, None) is not None

    def purge_expired(self) -> int:
        cutoff = time.perf_counter() - self._ttl
        with self._lock:
            stale = [k for k, v in self._items.items() if v.last_access < cutoff]
            for k in stale:
                del self._items[k]
            return len(stale)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
