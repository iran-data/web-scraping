import json
from decimal import Decimal
from pathlib import Path

import pytest

from web_scraping.adapters.bama import BamaAdapter
from web_scraping.adapters.hamrah_mechanic import HamrahMechanicAdapter
from web_scraping.exceptions import LayoutChangedError, UnsupportedFeatureError
from web_scraping.models import Availability, CarPriceType

FIXTURES = Path(__file__).parent / "fixtures"


def load(shop: str, name: str) -> dict[str, object]:
    return json.loads((FIXTURES / shop / f"{name}.json").read_text(encoding="utf-8"))


def test_bama_listing_parser_uses_visible_toman_price() -> None:
    product = BamaAdapter.parse_card(load("bama", "listing"))
    assert product.identifier == "epbnbimc"
    assert product.title == "پژو، 405 GLX دوگانه سوز 1390"
    assert product.current_price == Decimal("640000000")
    assert product.metadata["mileage_km"] == 250000


def test_bama_detail_parser_treats_mislabeled_json_ld_as_toman() -> None:
    product = BamaAdapter.parse_detail(
        load("bama", "product"),
        fallback_url="https://bama.ir/car/detail-epbnbimc",
    )
    assert product.current_price == Decimal("640000000")
    assert product.currency == "IRT"
    assert product.brand == "پژو"


def test_bama_car_price_parser_preserves_factory_and_market_types() -> None:
    payload = load("bama", "prices")
    group = payload["data"][0]  # type: ignore[index]
    factory = BamaAdapter.parse_car_price(group["items"][0])  # type: ignore[index]
    market = BamaAdapter.parse_car_price(group["items"][1])  # type: ignore[index]
    assert factory.price == Decimal("1502000000")
    assert factory.price_type == CarPriceType.FACTORY
    assert factory.currency == "IRT"
    assert market.price_type == CarPriceType.MARKET
    assert market.price_change_percentage == Decimal("0.64")


@pytest.mark.asyncio
async def test_bama_car_prices_builds_typed_page_without_browser_navigation() -> None:
    payload = load("bama", "prices")

    class StubBama(BamaAdapter):
        async def _get_json(self, url: str) -> dict[str, object]:
            assert "searchQuery=%D9%BE%DA%98%D9%88" in url
            assert "priceType=FactoryPrice" in url
            return payload

    result = await StubBama().car_prices(
        "پژو",
        page=1,
        page_size=3,
        price_type=CarPriceType.FACTORY,
    )
    assert len(result.items) == 2
    assert result.last_updated == "دیروز"
    assert result.next_page is None


@pytest.mark.parametrize("page,page_size", [(0, 3), (1, 0), (1, 101)])
@pytest.mark.asyncio
async def test_bama_car_price_pagination_validation(page: int, page_size: int) -> None:
    with pytest.raises(ValueError):
        await BamaAdapter().car_prices(page=page, page_size=page_size)


def test_vehicle_parsers_raise_on_missing_contract_fields() -> None:
    with pytest.raises(LayoutChangedError, match="Bama car price"):
        BamaAdapter.parse_car_price({})
    with pytest.raises(LayoutChangedError, match="listing"):
        HamrahMechanicAdapter.parse_listing({})
    with pytest.raises(LayoutChangedError, match="detail"):
        HamrahMechanicAdapter.parse_detail({}, fallback_url="https://example.test")


@pytest.mark.asyncio
async def test_bama_rejects_unverified_listing_pagination() -> None:
    adapter = BamaAdapter()
    with pytest.raises(UnsupportedFeatureError, match="infinite-scroll"):
        await adapter.search("پژو", page=2)


def test_hamrah_mechanic_listing_parser() -> None:
    product = HamrahMechanicAdapter.parse_listing(load("hamrahmechanic", "listing"))
    assert product.identifier == "3286814"
    assert product.current_price == Decimal("3430000000")
    assert product.original_price == Decimal("3600000000")
    assert product.discount_percentage == 5
    assert product.availability == Availability.IN_STOCK


def test_hamrah_mechanic_detail_parser() -> None:
    product = HamrahMechanicAdapter.parse_detail(
        load("hamrahmechanic", "product"),
        fallback_url="https://www.hamrah-mechanic.com/cars-for-sale/x/x/3286814/",
    )
    assert product.identifier == "3286814"
    assert product.brand == "ایران خودرو"
    assert product.metadata["mileage_km"] == 17203
    assert product.seller == "همراه مکانیک"
