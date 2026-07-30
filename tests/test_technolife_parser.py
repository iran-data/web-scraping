import json
from decimal import Decimal
from pathlib import Path

import pytest

from web_scraping.adapters.technolife import TechnolifeAdapter
from web_scraping.exceptions import LayoutChangedError
from web_scraping.models import Availability

FIXTURES = Path(__file__).parent / "fixtures" / "technolife"


def test_parse_search_payload() -> None:
    payload = json.loads((FIXTURES / "search.json").read_text(encoding="utf-8"))
    result = TechnolifeAdapter.parse_search_payload(payload, requested_page=1)
    assert result.total == 31
    assert result.has_next
    assert result.next_page == 2
    product = result.items[0]
    assert product.identifier == "165916"
    assert product.current_price == Decimal("137200000")
    assert product.original_price == Decimal("140000000")
    assert product.discount_percentage == Decimal("2")
    assert product.currency == "IRT"
    assert product.availability == Availability.IN_STOCK
    assert product.review_count == 151


def test_parse_product_payload_uses_technolife_toman_values() -> None:
    payload = json.loads((FIXTURES / "product.json").read_text(encoding="utf-8"))
    product = TechnolifeAdapter.parse_product_payload(
        payload, fallback_url="https://www.technolife.com/product-165916/"
    )
    assert product.identifier == "165916"
    assert product.current_price == Decimal("137200000")
    assert product.seller == "هماهنگ شاپ"
    assert product.brand == "سامسونگ"
    assert product.rating == 4
    assert product.availability == Availability.IN_STOCK


def test_product_identifier_url() -> None:
    adapter = TechnolifeAdapter()
    assert adapter.product_url("TLP-165916").endswith("/product-165916/")
    with pytest.raises(ValueError):
        adapter.product_url("not-an-id")


def test_search_layout_change_is_explicit() -> None:
    with pytest.raises(LayoutChangedError, match="dehydratedState"):
        TechnolifeAdapter.parse_search_payload({}, requested_page=1)
