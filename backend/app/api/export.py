"""CSV downloads: the cleaned catalogue and the quality report."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import Response

from app.api.upload import get_catalogue_or_404
from app.services import export_service as ex

router = APIRouter(prefix="/api/catalogue", tags=["export"])


def _csv_response(data: bytes, filename: str) -> Response:
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{catalogue_id}/export")
def export_cleaned(catalogue_id: str):
    """Working copy as CSV: original columns and order, only approved/edited changes applied."""
    cat = get_catalogue_or_404(catalogue_id)
    data, _ = ex.cleaned_csv(cat)
    return _csv_response(data, ex.safe_filename(cat.filename, "cleaned"))


@router.get("/{catalogue_id}/report")
def export_report(catalogue_id: str):
    """One row per issue, with original/final value, decision and resolution status."""
    cat = get_catalogue_or_404(catalogue_id)
    data, _ = ex.report_csv(cat)
    return _csv_response(data, ex.safe_filename(cat.filename, "quality_report"))
