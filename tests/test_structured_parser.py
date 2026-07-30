import json
from decimal import Decimal
from pathlib import Path

import pytest

from web_scraping.adapters.parser import json_ld_products, load_json, walk_json
from web_scraping.adapters.technolife import TechnolifeAdapter
from web_scraping.exceptions import ParsingError
from web_scraping.models import Availability


def test_schema_org_product_parser() -> None:
    fixture = Path(__file__).parent / "fixtures" / "structured" / "product.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    adapter = TechnolifeAdapter()
    product = adapter._parse_json_ld(data, fallback_url="https://example.test/fallback")
    assert product.identifier == "abc-42"
    assert product.title == "گوشی موبایل آزمایشی"
    assert product.current_price == Decimal("120000")
    assert product.discount_percentage == Decimal("20.00")
    assert product.rating == 4.2
    assert product.review_count == 12
    assert product.availability == Availability.IN_STOCK


def test_structured_json_helpers_find_nested_product_types() -> None:
    payload = {
        "@graph": [
            {"@type": "Organization"},
            {"node": {"@type": ["Thing", "Product"], "name": "nested"}},
        ]
    }
    walked = list(walk_json(payload))
    products = json_ld_products(payload)
    assert len(walked) == 4
    assert [product["name"] for product in products] == ["nested"]


def test_invalid_structured_json_has_source_context() -> None:
    with pytest.raises(ParsingError, match="fixture-script"):
        load_json("{broken", source="fixture-script")


def test_structured_card_parser_handles_missing_and_out_of_stock_values() -> None:
    adapter = TechnolifeAdapter()
    assert adapter._parse_card({"href": None, "title": "x"}) is None
    product = adapter._parse_card(
        {
            "href": "/product-42/example",
            "title": "  کالای آزمایشی ",
            "image": "/image.jpg",
            "text": "ناموجود",
        }
    )
    assert product is not None
    assert product.identifier == "42"
    assert product.image_url == "https://www.technolife.com/image.jpg"
    assert product.current_price is None
    assert product.availability == Availability.OUT_OF_STOCK


def test_structured_helpers_handle_identifier_and_discount_edges() -> None:
    adapter = TechnolifeAdapter()
    assert adapter.identifier_from_url("https://example.test/products/no-number") == "no-number"
    assert adapter._discount(80, 100) == Decimal("20.00")
    assert adapter._discount(100, 80) is None
