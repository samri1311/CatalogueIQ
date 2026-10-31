"""Request / response schemas for the HTTP API."""
from __future__ import annotations

from pydantic import BaseModel

from app.models.issue import Issue, ReviewAction


class UploadResponse(BaseModel):
    catalogue_id: str
    filename: str
    row_count: int
    columns: list[str]
    preview: list[dict[str, str]]
    suggested_mapping: dict[str, str]
    standard_fields: list[str]
    required_fields: list[str]


class CellState(BaseModel):
    severity: str | None  # highest severity among problems still present
    state: str  # "open" | "dismissed" (rejected/ignored only) | "resolved"
    issue_ids: list[str]


class CataloguePage(BaseModel):
    catalogue_id: str
    filename: str
    columns: list[str]
    mapping: dict[str, str]
    checked_columns: list[str]  # columns covered by a mapped-field rule
    analyzed: bool
    total_rows: int  # rows matching the current filters
    offset: int
    limit: int
    rows: list[dict[str, str]]  # each row also carries "__row_id__"
    cells: dict[str, dict[str, CellState]]  # row_id -> column -> state


class AnalyzeRequest(BaseModel):
    mapping: dict[str, str] | None = None


class AnalysisSummary(BaseModel):
    catalogue_id: str
    total_products: int
    total_issues: int
    errors: int  # errors/warnings/infos/flagged_* count problems still present
    warnings: int
    infos: int
    flagged_cells: int
    flagged_rows: int
    by_type: dict[str, int]
    by_status: dict[str, int]
    # Possible duplicates from the last similarity run; None if it has not been run.
    potential_duplicates: int | None = None
    unmapped_required_fields: list[str]


class IssueList(BaseModel):
    catalogue_id: str
    total: int
    issues: list[Issue]


class ReviewRequest(BaseModel):
    action: ReviewAction
    value: str | None = None  # required for "edit"


class ReviewResponse(BaseModel):
    issue: Issue
    changed_issues: list[Issue]  # includes issues resolved/reopened/created by revalidation
    row_id: int
    column: str
    original_value: str
    current_value: str


class ChangedCell(BaseModel):
    row_id: int
    sku: str | None
    column: str
    original_value: str
    current_value: str
    issue_ids: list[str]
    review_actions: list[str]


class ComparisonResponse(BaseModel):
    catalogue_id: str
    changed_cells: list[ChangedCell]
    unresolved_issues: list[Issue]
    dismissed_issues: list[Issue]
    resolved_count: int
