from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from web_scraping.adapters.digikala import DigikalaAdapter
from web_scraping.adapters.digikalajet import DigikalaJetAdapter
from web_scraping.adapters.snappmarket import SnappMarketAdapter
from web_scraping.adapters.torob import TorobAdapter
from web_scraping.exceptions import LayoutChangedError
from web_scraping.models import SortOption

FIXTURES = Path(__file__).parent / "fixtures"


def load(shop: str, name: str = "search") -> dict[str, Any]:
    return json.loads((FIXTURES / shop / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.asyncio
async def test_digikala_search_and_detail_build_verified_api_urls() -> None:
    search_payload = load("digikala")
    detail_payload = load("digikala", "product")
    urls: list[str] = []

    class Stub(DigikalaAdapter):
        async def _get_json(self, url: str) -> dict[str, Any]:
            urls.append(url)
            return detail_payload if "/v2/product/" in url else search_payload

    adapter = Stub()
    result = await adapter.search(
        "گوشی",
        page=2,
        sort=SortOption.CHEAPEST,
        filters={"brands[]": [18, 20]},
    )
    detail = await adapter.get_product("https://www.digikala.com/product/dkp-22258282/")
    assert result.items
    assert result.page == 1  # fixture contract controls the normalized current page
    assert "page=2" in urls[0] and "sort=20" in urls[0]
    assert "brands%5B%5D=18" in urls[0] and "brands%5B%5D=20" in urls[0]
    assert urls[1].endswith("/v2/product/22258282/")
    assert detail.identifier == "22258282"


@pytest.mark.asyncio
async def test_digikala_search_layout_failure_is_explicit() -> None:
    class Stub(DigikalaAdapter):
        async def _get_json(self, url: str) -> dict[str, Any]:
            return {}

    with pytest.raises(LayoutChangedError, match="widgets"):
        await Stub().search("گوشی")


@pytest.mark.asyncio
async def test_jet_search_and_detail_keep_location_and_composite_id() -> None:
    search_payload = load("digikalajet")
    item = search_payload["data"]["result"][0]
    urls: list[str] = []

    class Stub(DigikalaJetAdapter):
        async def _get_json(self, url: str) -> dict[str, Any]:
            urls.append(url)
            if "/shop/" in url:
                return {"data": {"product": item}}
            return search_payload

    adapter = Stub()
    result = await adapter.search("شیر", sort=SortOption.CHEAPEST)
    detail = await adapter.get_product(result.items[0].identifier)
    assert result.items
    assert "latitude=35.7005" in urls[0] and "sort=20" in urls[0]
    assert "/shop/185113440676/product/22122708/" in urls[1]
    assert detail.identifier == result.items[0].identifier


@pytest.mark.asyncio
async def test_snappmarket_search_and_detail_use_pwa_contract() -> None:
    search_payload = load("snappmarket")
    item = search_payload["items"][0]
    detail_payload = {
        **item,
        "min_price": item["price"],
        "discount_ratio": item["discountRatio"],
        "brand_title": "ماهشام",
    }
    urls: list[str] = []

    class Stub(SnappMarketAdapter):
        async def _get_json(self, url: str) -> dict[str, Any]:
            urls.append(url)
            return detail_payload if "/pb/products/" in url else search_payload

    adapter = Stub()
    result = await adapter.search("شیر", page=2)
    detail = await adapter.get_product(result.items[0].identifier)
    assert result.page == 2
    assert "page=1" in urls[0] and "client=PWA" in urls[0]
    assert "lat=35.700500" in urls[0] and "long=51.391700" in urls[0]
    assert detail.brand == "ماهشام"


@pytest.mark.asyncio
async def test_torob_search_and_detail_build_uuid_contract() -> None:
    payload = load("torob")
    item = payload["results"][0]
    urls: list[str] = []

    class Stub(TorobAdapter):
        async def _get_json(self, url: str) -> dict[str, Any]:
            urls.append(url)
            return item if "/details/" in url else payload

    adapter = Stub()
    result = await adapter.search("موبایل", page=2, sort=SortOption.CHEAPEST)
    detail = await adapter.get_product(result.items[0].url)
    assert result.page == 2
    assert "page=1" in urls[0] and "sort=price" in urls[0]
    assert "prk=" in urls[1]
    assert detail.identifier == result.items[0].identifier
