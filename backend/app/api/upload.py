"""Upload and catalogue-read endpoints."""
from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, File, HTTPException, Query, UploadFile

from app.deps import settings, store
from app.models.issue import Severity
from app.services import issue_manager as im
from app.models.schemas import CataloguePage, UploadResponse
from app.services import csv_loader as loader

router = APIRouter(prefix="/api", tags=["catalogue"])


def get_catalogue_or_404(catalogue_id: str):
    cat = store.get(catalogue_id)
    if cat is None:
        raise HTTPException(404, "Catalogue not found or expired. Please upload it again.")
    return cat


@router.post("/upload", response_model=UploadResponse)
async def upload(file: UploadFile = File(...)):
    try:
        loader.validate_filename(file.filename)
        # Read one byte past the limit so oversized files are rejected
        # without buffering an arbitrarily large body.
        data = await file.read(settings.max_upload_bytes + 1)
        df = loader.load_csv(data, settings)
    except loader.CsvLoadError as exc:
        raise HTTPException(400, str(exc)) from exc
    finally:
        await file.close()  # releases any temp file Starlette spooled to disk

    columns = list(df.columns)
    mapping = loader.suggest_mapping(columns)
    cat = store.create(file.filename, df, mapping)
    return UploadResponse(
        catalogue_id=cat.catalogue_id,
        filename=cat.filename,
        row_count=len(df),
        columns=columns,
        preview=df.head(settings.preview_rows).to_dict(orient="records"),
        suggested_mapping=mapping,
        standard_fields=loader.STANDARD_FIELDS,
        required_fields=loader.REQUIRED_FIELDS,
    )


@router.get("/catalogue/{catalogue_id}", response_model=CataloguePage)
def get_catalogue(catalogue_id: str, offset: int = Query(0, ge=0),
                  limit: int = Query(50, ge=1, le=500),
                  q: str | None = Query(None, max_length=200),
                  severity: Severity | None = None,
                  flagged_only: bool = False):
    """Working-copy rows (with per-cell issue state), filtered and paginated."""
    cat = get_catalogue_or_404(catalogue_id)
    df = cat.working
    mask = pd.Series(True, index=df.index)
    if q:
        mask &= df.apply(lambda c: c.str.contains(q, case=False, regex=False)).any(axis=1)
    if flagged_only or severity is not None:
        mask &= df.index.isin(sorted(im.rows_with_open_issues(cat, severity)))
    ids = df.index[mask]
    page = df.loc[ids[offset: offset + limit]]
    rows = [{"__row_id__": str(rid), **rec}
            for rid, rec in zip(page.index, page.to_dict(orient="records"))]
    return CataloguePage(
        catalogue_id=cat.catalogue_id, filename=cat.filename,
        columns=list(df.columns), mapping=cat.mapping,
        checked_columns=list(cat.mapping.values()),
        analyzed=cat.analyzed, total_rows=len(ids),
        offset=offset, limit=limit, rows=rows,
        cells=im.cell_states(cat, [int(r) for r in page.index]),
    )


@router.delete("/catalogue/{catalogue_id}", status_code=204)
def delete_catalogue(catalogue_id: str):
    if not store.delete(catalogue_id):
        raise HTTPException(404, "Catalogue not found or expired.")
