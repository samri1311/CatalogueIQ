"""Similar-product candidates for human review. Nothing is merged or changed."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.upload import get_catalogue_or_404
from app.deps import get_embedder, settings
from app.intelligence.duplicate_detector import DetectionParams, detect
from app.intelligence.embedding_service import EmbeddingModelError, EmbeddingService
from app.models.similarity import (
    CandidateReviewRequest, CandidateStatus, Relationship, SimilarCandidate,
    SimilarityParams, SimilarityResponse,
)

router = APIRouter(prefix="/api/catalogue", tags=["similarity"])


@router.get("/{catalogue_id}/similar-products", response_model=SimilarityResponse)
def similar_products(
    catalogue_id: str,
    semantic: bool = True,
    semantic_threshold: float = Query(settings.semantic_threshold, ge=0, le=1),
    fuzzy_threshold: float = Query(settings.fuzzy_threshold, ge=0, le=100),
    top_k: int = Query(settings.similarity_top_k, ge=1, le=50),
    embedder: EmbeddingService = Depends(get_embedder),
):
    cat = get_catalogue_or_404(catalogue_id)
    if "product_name" not in cat.mapping:
        raise HTTPException(409, "Map the product_name column before looking for similar products.")
    if len(cat.working) > settings.max_similarity_rows:
        raise HTTPException(
            413, f"Similarity search supports up to {settings.max_similarity_rows} products "
                 f"(this catalogue has {len(cat.working)}).")

    params = DetectionParams(semantic_threshold, fuzzy_threshold, top_k, use_semantic=semantic)
    try:
        # Uses the working copy, so accepted corrections are reflected in the matching.
        result = detect(cat.working, cat.mapping, params, embedder if semantic else None, cat.embeddings)
    except EmbeddingModelError as exc:
        raise HTTPException(503, str(exc)) from exc

    for c in result.candidates:
        c.review_status = cat.candidate_reviews.get(c.candidate_id, CandidateStatus.pending)
    cat.known_candidates = {c.candidate_id for c in result.candidates}
    cat.potential_duplicates = sum(
        1 for c in result.candidates
        if c.relationship == Relationship.possible_duplicate
        and c.review_status != CandidateStatus.not_duplicate)

    return SimilarityResponse(
        catalogue_id=cat.catalogue_id,
        params=SimilarityParams(semantic_threshold=semantic_threshold,
                                fuzzy_threshold=fuzzy_threshold, top_k=top_k,
                                semantic_enabled=semantic),
        compared_rows=result.compared_rows, skipped_rows=result.skipped_rows,
        model=embedder.model_name if semantic else None,
        candidates=result.candidates,
    )


@router.post("/{catalogue_id}/similar-products/{candidate_id}/review")
def review_candidate(catalogue_id: str, candidate_id: str, body: CandidateReviewRequest):
    """Record the user's judgement. This never modifies or merges catalogue rows."""
    cat = get_catalogue_or_404(catalogue_id)
    if candidate_id not in cat.known_candidates:
        raise HTTPException(404, "Candidate not found. Run the similarity search first.")
    cat.candidate_reviews[candidate_id] = body.status
    return {"candidate_id": candidate_id, "review_status": body.status}
