import json
from collections.abc import Callable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from web_scraping.adapters.digikalajet import DigikalaJetAdapter
from web_scraping.adapters.snappmarket import SnappMarketAdapter
from web_scraping.adapters.torob import TorobAdapter
from web_scraping.exceptions import LayoutChangedError, UnsupportedFeatureError
from web_scraping.models import Availability, Product, SortOption

FIXTURES = Path(__file__).parent / "fixtures"


def load(shop: str) -> dict[str, object]:
    return json.loads((FIXTURES / shop / "search.json").read_text(encoding="utf-8"))


def test_digikalajet_product_parser_converts_rial_to_toman() -> None:
    data = load("digikalajet")["data"]
    product = DigikalaJetAdapter.parse_product(data["result"][0])  # type: ignore[index]
    assert product.identifier == "185113440676:22122708"
    assert product.current_price == Decimal("138500")
    assert product.currency == "IRT"
    assert product.availability == Availability.IN_STOCK


def test_snappmarket_search_product_parser_uses_toman() -> None:
    item = load("snappmarket")["items"][0]  # type: ignore[index]
    product = SnappMarketAdapter.parse_search_product(item)  # type: ignore[arg-type]
    assert product.identifier == "9703920"
    assert product.current_price == Decimal("117725")
    assert product.original_price == Decimal("138500")
    assert product.discount_percentage == 15


@pytest.mark.asyncio
async def test_snappmarket_rejects_unverified_sort_before_request() -> None:
    adapter = SnappMarketAdapter()
    with pytest.raises(UnsupportedFeatureError, match="does not expose a verified"):
        await adapter.search("شیر", sort=SortOption.CHEAPEST)


def test_torob_product_parser_uses_toman_and_uuid() -> None:
    item = load("torob")["results"][0]  # type: ignore[index]
    product = TorobAdapter.parse_product(item)  # type: ignore[arg-type]
    assert product.identifier == "153df520-3821-4053-ba6c-b55dbdd32f1a"
    assert product.current_price == Decimal("128999000")
    assert product.url.startswith("https://torob.com/p/")


@pytest.mark.parametrize(
    ("parser", "payload", "message"),
    [
        (DigikalaJetAdapter.parse_product, {}, "missing"),
        (SnappMarketAdapter.parse_search_product, {}, "missing"),
        (SnappMarketAdapter.parse_product_payload, {}, "missing"),
        (TorobAdapter.parse_product, {}, "missing"),
    ],
)
def test_remaining_adapter_layout_changes_are_explicit(
    parser: Callable[[Mapping[str, Any]], Product],
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(LayoutChangedError, match=message):
        parser(payload)
