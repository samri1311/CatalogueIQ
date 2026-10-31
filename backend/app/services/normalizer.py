"""Small, deterministic text helpers used by the quality engine.

Nothing here guesses facts: every function either returns a clearly
justified normalization or None.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

_STRICT_DECIMAL = re.compile(r"^[+-]?\d+(\.\d+)?$")
_STRICT_INT = re.compile(r"^[+-]?\d+$")
_THOUSANDS = re.compile(r"^\d{1,3}(,\d{3})+(\.\d+)?$")
_CURRENCY_SYMBOLS = "$€£₹¥"

# Common ISO 4217 codes. Extend as needed.
ISO_CURRENCIES = {
    "USD", "EUR", "GBP", "INR", "JPY", "CNY", "AUD", "CAD", "CHF", "SEK", "NOK",
    "DKK", "NZD", "SGD", "HKD", "KRW", "MXN", "BRL", "ZAR", "AED", "SAR", "PLN",
    "CZK", "HUF", "TRY", "THB", "IDR", "MYR", "PHP", "ILS", "RUB",
}

# Known category spellings -> canonical form (keys are casefolded).
CATEGORY_MAP = {
    "tshirt": "T-Shirts", "tshirts": "T-Shirts", "t-shirt": "T-Shirts",
    "t shirt": "T-Shirts", "t shirts": "T-Shirts",
    "sneaker": "Sneakers", "trainers": "Sneakers",
    "jean": "Jeans", "denim": "Jeans",
    "laptop": "Laptops", "notebook computers": "Laptops",
    "mobile phones": "Smartphones", "cell phones": "Smartphones",
}


def is_blank(value: str) -> bool:
    return value.strip() == ""


def parse_decimal_strict(value: str) -> float | None:
    v = value.strip()
    return float(v) if _STRICT_DECIMAL.match(v) else None


def parse_int_strict(value: str) -> int | None:
    v = value.strip()
    return int(v) if _STRICT_INT.match(v) else None


def clean_price_text(value: str) -> str | None:
    """Strip one currency symbol and thousands commas ("$1,299.50" -> "1299.50").

    Returns None when the result is still not a plain decimal. European
    formats such as "1.299,50" are ambiguous and deliberately not converted.
    """
    v = value.strip()
    if v and v[0] in _CURRENCY_SYMBOLS:
        v = v[1:].strip()
    if _THOUSANDS.match(v):
        v = v.replace(",", "")
    return v if _STRICT_DECIMAL.match(v) and v != value.strip() else None


def is_valid_url(value: str) -> bool:
    v = value.strip()
    if not v or re.search(r"\s", v):
        return False
    try:
        parsed = urlparse(v)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc) and "." in parsed.netloc


def normalize_key(value: str) -> str:
    """Key for comparing values that differ only by case/whitespace."""
    return re.sub(r"\s+", " ", value.strip()).casefold()
