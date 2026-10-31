"""Review actions on individual issues, and the before/after comparison."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.api.upload import get_catalogue_or_404
from app.deps import store
from app.models.issue import ReviewAction
from app.models.schemas import ComparisonResponse, ReviewRequest, ReviewResponse
from app.services import issue_manager as im

router = APIRouter(prefix="/api", tags=["review"])


def _cat_for_issue(issue_id: str):
    cat = store.find_by_issue(issue_id)
    if cat is None:
        raise HTTPException(404, "Issue not found or its catalogue has expired.")
    return cat


def _response(cat, issue, changed) -> ReviewResponse:
    return ReviewResponse(
        issue=issue, changed_issues=changed, row_id=issue.row_id, column=issue.column,
        original_value=cat.original.at[issue.row_id, issue.column],
        current_value=cat.working.at[issue.row_id, issue.column],
    )


@router.post("/issues/{issue_id}/review", response_model=ReviewResponse)
def review(issue_id: str, body: ReviewRequest):
    if body.action == ReviewAction.undo:
        raise HTTPException(400, "Use POST /api/issues/{issue_id}/undo to undo.")
    cat = _cat_for_issue(issue_id)
    try:
        issue, changed = im.review_issue(cat, issue_id, body.action, body.value)
    except im.ReviewError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return _response(cat, issue, changed)


@router.post("/issues/{issue_id}/undo", response_model=ReviewResponse)
def undo(issue_id: str):
    cat = _cat_for_issue(issue_id)
    try:
        issue, changed = im.undo_issue(cat, issue_id)
    except im.ReviewError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    return _response(cat, issue, changed)


@router.get("/catalogue/{catalogue_id}/comparison", response_model=ComparisonResponse)
def comparison(catalogue_id: str):
    cat = get_catalogue_or_404(catalogue_id)
    return im.comparison(cat)
