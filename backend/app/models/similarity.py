"""Models for similar-product candidates. Candidates are suggestions only."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class CandidateStatus(str, Enum):
    pending = "pending"
    duplicate = "duplicate"  # user judged it a duplicate (nothing is merged automatically)
    not_duplicate = "not_duplicate"
    needs_investigation = "needs_investigation"


class Relationship(str, Enum):
    possible_duplicate = "possible_duplicate"
    # Similar text but a hard attribute (size, colour, material, brand) differs.
    possible_variant = "possible_variant"


class SimilarCandidate(BaseModel):
    candidate_id: str
    source_row_id: int
    candidate_row_id: int
    source_sku: str | None
    candidate_sku: str | None
    source_name: str
    candidate_name: str
    semantic_score: float | None  # cosine similarity, 0..1 (None if semantic matching was off)
    fuzzy_score: float | None  # RapidFuzz token-sort ratio on product names, 0..100
    matching_fields: list[str]
    differing_fields: list[str]
    relationship: Relationship
    reason: str
    review_status: CandidateStatus = CandidateStatus.pending


class SimilarityParams(BaseModel):
    semantic_threshold: float
    fuzzy_threshold: float
    top_k: int
    semantic_enabled: bool


class SimilarityResponse(BaseModel):
    catalogue_id: str
    params: SimilarityParams
    compared_rows: int
    skipped_rows: int  # rows with no usable name/text
    model: str | None
    candidates: list[SimilarCandidate]


class CandidateReviewRequest(BaseModel):
    status: CandidateStatus
