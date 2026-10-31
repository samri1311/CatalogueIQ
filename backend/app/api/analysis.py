"""Quality analysis, summary and issue listing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.api.upload import get_catalogue_or_404
from app.models.issue import IssueType, Severity
from app.models.schemas import AnalysisSummary, AnalyzeRequest, IssueList
from app.services import csv_loader as loader
from app.services import issue_manager as im
from app.services import quality_engine

router = APIRouter(prefix="/api/catalogue", tags=["analysis"])


@router.post("/{catalogue_id}/analyze", response_model=AnalysisSummary)
def analyze(catalogue_id: str, body: AnalyzeRequest | None = None):
    """(Re)run the checks on the original upload.

    This starts the review over: the working copy is reset to the original
    and all previous review decisions are discarded.
    """
    cat = get_catalogue_or_404(catalogue_id)
    if body and body.mapping is not None:
        try:
            cat.mapping = loader.validate_mapping(body.mapping, list(cat.original.columns))
        except loader.CsvLoadError as exc:
            raise HTTPException(400, str(exc)) from exc

    cat.reset_review_state()
    cat.issues = quality_engine.analyze(cat.original, cat.mapping)
    cat.analyzed = True
    return im.summarize(cat)


@router.get("/{catalogue_id}/summary", response_model=AnalysisSummary)
def summary(catalogue_id: str):
    cat = get_catalogue_or_404(catalogue_id)
    if not cat.analyzed:
        raise HTTPException(409, "Catalogue has not been analyzed yet.")
    return im.summarize(cat)


@router.get("/{catalogue_id}/issues", response_model=IssueList)
def list_issues(catalogue_id: str, severity: Severity | None = None,
                issue_type: IssueType | None = None, column: str | None = None,
                row_id: int | None = Query(None, ge=0), status: str | None = None):
    cat = get_catalogue_or_404(catalogue_id)
    if not cat.analyzed:
        raise HTTPException(409, "Catalogue has not been analyzed yet.")
    issues = [
        i for i in cat.issues
        if (severity is None or i.severity == severity)
        and (issue_type is None or i.issue_type == issue_type)
        and (column is None or i.column == column)
        and (row_id is None or i.row_id == row_id)
        and (status is None or i.status.value == status)
    ]
    return IssueList(catalogue_id=cat.catalogue_id, total=len(issues), issues=issues)
