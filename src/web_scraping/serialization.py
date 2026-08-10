"""JSON-safe serialization for public models."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


def jsonable(value: Any) -> Any:
    if isinstance(value, (Decimal, date, datetime)):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return jsonable(asdict(value))
    return value
