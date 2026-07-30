"""Utilities for extracting structured page data."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

from web_scraping.exceptions import ParsingError


def load_json(text: str, *, source: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise ParsingError(f"Invalid JSON in {source}: {error}") from error


def walk_json(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def json_ld_products(value: Any) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for item in walk_json(value):
        item_type = item.get("@type")
        if item_type == "Product" or (isinstance(item_type, list) and "Product" in item_type):
            products.append(item)
    return products
