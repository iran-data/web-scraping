"""Normalization helpers for Persian commerce data."""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_LETTER_MAP = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک"})
_SPACE_RE = re.compile(r"\s+")
_NON_NUMBER_RE = re.compile(r"[^\d.,-]")


def normalize_digits(value: str) -> str:
    return value.translate(_DIGIT_MAP)


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = unicodedata.normalize("NFKC", value).translate(_LETTER_MAP)
    normalized = normalized.replace("\u200cی", "ی").replace("\u200c", " ")
    normalized = _SPACE_RE.sub(" ", normalized).strip()
    return normalized or None


def parse_number(value: object) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    text = normalize_digits(str(value))
    cleaned = _NON_NUMBER_RE.sub("", text).replace(",", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def parse_int(value: object) -> int | None:
    number = parse_number(value)
    return int(number) if number is not None else None


def normalize_price(value: object, *, source_currency: str = "IRR") -> Decimal | None:
    """Normalize a price to Iranian toman (IRT).

    Rial values are divided by ten. Toman values are returned unchanged.
    """
    number = parse_number(value)
    if number is None:
        return None
    currency = source_currency.upper()
    if currency in {"IRT", "TOMAN", "تومان"}:
        return number
    if currency in {"IRR", "RIAL", "ریال"}:
        return number / 10
    return number


def normalize_rating(value: object, *, source_max: float = 5.0) -> float | None:
    number = parse_number(value)
    if number is None or source_max <= 0:
        return None
    rating = float(number) * 5 / source_max
    return min(5.0, max(1.0, round(rating, 2)))


def absolute_url(base_url: str, value: str | None) -> str | None:
    text = normalize_text(value)
    return urljoin(base_url, text) if text else None
