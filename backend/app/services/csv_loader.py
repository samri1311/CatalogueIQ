"""Safe CSV loading and column mapping.

Every cell is read as a string and nothing is coerced or dropped, so the
uploaded values, column names, column order and row order are preserved.
"""
from __future__ import annotations

import csv
import io
import re

import pandas as pd

from app.config import Settings

STANDARD_FIELDS = [
    "sku", "product_name", "description", "category", "brand", "price",
    "currency", "color", "material", "size", "stock_quantity",
    "product_url", "image_url",
]
REQUIRED_FIELDS = ["sku", "product_name", "category", "price"]

# Extra header spellings recognised when suggesting a mapping.
_ALIASES = {
    "sku": ["sku", "product_sku", "item_sku", "item_code", "product_code", "id", "product_id"],
    "product_name": ["product_name", "name", "title", "product_title", "product", "item_name"],
    "description": ["description", "desc", "product_description", "details"],
    "category": ["category", "product_category", "type", "product_type", "department"],
    "brand": ["brand", "manufacturer", "vendor", "make"],
    "price": ["price", "unit_price", "cost", "amount", "selling_price", "mrp"],
    "currency": ["currency", "currency_code", "curr"],
    "color": ["color", "colour"],
    "material": ["material", "fabric"],
    "size": ["size", "product_size"],
    "stock_quantity": ["stock_quantity", "stock", "quantity", "qty", "inventory", "stock_qty"],
    "product_url": ["product_url", "url", "link", "product_link", "page_url"],
    "image_url": ["image_url", "image", "img_url", "image_link", "photo_url"],
}


class CsvLoadError(ValueError):
    """Raised for any problem with the uploaded file; message is user-safe."""


def _canon(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")


def decode_bytes(data: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise CsvLoadError("File is not valid UTF-8 or Windows-1252 text.")


def validate_filename(filename: str | None) -> None:
    if not filename or not filename.lower().endswith(".csv"):
        raise CsvLoadError("Only .csv files are supported.")


def load_csv(data: bytes, settings: Settings) -> pd.DataFrame:
    """Parse CSV bytes into an all-string DataFrame, enforcing limits."""
    if not data:
        raise CsvLoadError("The file is empty.")
    if len(data) > settings.max_upload_bytes:
        raise CsvLoadError(
            f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB size limit."
        )
    if b"\x00" in data:
        raise CsvLoadError("File appears to be binary, not a CSV.")

    text = decode_bytes(data)
    reader = csv.reader(io.StringIO(text))
    try:
        header = next(reader, None)
    except csv.Error as exc:
        raise CsvLoadError(f"Malformed CSV: {exc}") from exc
    if not header or all(not h.strip() for h in header):
        raise CsvLoadError("The file has no header row.")
    if any(not h.strip() for h in header):
        raise CsvLoadError("The header row contains an empty column name.")
    if len(header) > settings.max_columns:
        raise CsvLoadError(f"File has more than {settings.max_columns} columns.")
    dupes = sorted({h for h in header if header.count(h) > 1})
    if dupes:
        raise CsvLoadError(f"Duplicate column names are not supported: {', '.join(dupes)}.")

    # Rows are validated one by one rather than via pandas, which would
    # silently shift columns (extra fields) or pad (missing fields).
    rows: list[list[str]] = []
    try:
        for row in reader:
            if not row:  # fully blank line
                continue
            if len(row) != len(header):
                raise CsvLoadError(
                    f"Malformed CSV: line {reader.line_num} has {len(row)} fields, "
                    f"expected {len(header)}."
                )
            rows.append(row)
            if len(rows) > settings.max_rows:
                raise CsvLoadError(f"File has more than {settings.max_rows} rows.")
    except csv.Error as exc:
        raise CsvLoadError(f"Malformed CSV: {exc}") from exc

    if not rows:
        raise CsvLoadError("The file has a header but no data rows.")
    return pd.DataFrame(rows, columns=header, dtype=str)


def suggest_mapping(columns: list[str]) -> dict[str, str]:
    """Map standard field -> CSV column using header names. Each column used once."""
    canon = {c: _canon(c) for c in columns}
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for field in STANDARD_FIELDS:
        for alias in _ALIASES[field]:
            match = next((c for c in columns if canon[c] == alias and c not in used), None)
            if match:
                mapping[field] = match
                used.add(match)
                break
    return mapping


def validate_mapping(mapping: dict[str, str], columns: list[str]) -> dict[str, str]:
    clean = {k: v for k, v in mapping.items() if v}
    for field, col in clean.items():
        if field not in STANDARD_FIELDS:
            raise CsvLoadError(f"Unknown standard field: {field}.")
        if col not in columns:
            raise CsvLoadError(f"Column '{col}' is not in the uploaded file.")
    if len(set(clean.values())) != len(clean):
        raise CsvLoadError("A CSV column can be mapped to only one standard field.")
    return clean
