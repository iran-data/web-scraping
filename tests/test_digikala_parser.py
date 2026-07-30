import json
from decimal import Decimal
from pathlib import Path

import pytest

from web_scraping.adapters.digikala import DigikalaAdapter
from web_scraping.exceptions import LayoutChangedError
from web_scraping.models import Availability

FIXTURES = Path(__file__).parent / "fixtures" / "digikala"


def test_parse_search_product() -> None:
    payload = json.loads((FIXTURES / "search.json").read_text(encoding="utf-8"))
    listing = payload["data"]["widgets"][0]["data"]
    data = next(item["data"] for item in listing["widgets"] if item["type"] == "product")
    product = DigikalaAdapter.parse_product(data)
    assert product.shop == "digikala"
    assert product.identifier.isdigit()
    assert product.title
    assert product.url.startswith("https://www.digikala.com/product/")
    assert isinstance(product.current_price, (Decimal, int))
    assert product.availability == Availability.IN_STOCK
    assert product.rating is None or 1 <= product.rating <= 5


def test_parse_product_detail() -> None:
    payload = json.loads((FIXTURES / "product.json").read_text(encoding="utf-8"))
    product = DigikalaAdapter.parse_product(payload["data"]["product"])
    assert product.identifier == "22258282"
    assert product.brand == "نوکیا"
    assert product.seller
    assert product.currency == "IRT"
    assert product.current_price == Decimal("3599000")


def test_layout_change_is_explicit() -> None:
    with pytest.raises(LayoutChangedError, match="required"):
        DigikalaAdapter.parse_product({"id": 1})
