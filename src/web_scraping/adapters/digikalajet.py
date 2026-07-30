"""Location-aware Digikala Jet adapter."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar
from urllib.parse import urlencode

from playwright.async_api import APIResponse

from web_scraping.adapters.base import BaseShopAdapter
from web_scraping.exceptions import LayoutChangedError, ProductNotFoundError
from web_scraping.models import Availability, Product, SearchPage, SortOption
from web_scraping.normalization import normalize_price, normalize_text, parse_int

_COMPOSITE_ID = re.compile(r"(?:(\d+):)?(\d+)")


class DigikalaJetAdapter(BaseShopAdapter):
    shop_name = "digikalajet"
    base_url = "https://www.digikalajet.com"
    api_url = "https://api.digikalajet.ir"
    latitude = 35.7005
    longitude = 51.3917
    sort_ids: ClassVar[dict[SortOption, int]] = {
        SortOption.RELEVANCE: 22,
        SortOption.NEWEST: 1,
        SortOption.CHEAPEST: 20,
        SortOption.MOST_EXPENSIVE: 21,
        SortOption.MOST_POPULAR: 22,
        SortOption.BEST_SELLING: 22,
    }

    async def search(
        self,
        keyword: str,
        *,
        page: int = 1,
        sort: SortOption = SortOption.RELEVANCE,
        filters: Mapping[str, str | int | bool | Sequence[str]] | None = None,
    ) -> SearchPage:
        if page < 1:
            raise ValueError("page must be at least 1")
        params: list[tuple[str, object]] = [
            ("q", keyword),
            ("shopId", ""),
            ("latitude", self.latitude),
            ("longitude", self.longitude),
            ("page", page),
            ("sort", self.sort_ids[sort]),
        ]
        for key, value in (filters or {}).items():
            if isinstance(value, Sequence) and not isinstance(value, str):
                params.extend((key, item) for item in value)
            else:
                params.append((key, value))
        payload = await self._get_json(
            f"{self.api_url}/products/search/all/?{urlencode(params, doseq=True)}"
        )
        try:
            data = payload["data"]
            results = data["result"]
            pager = data["pager"]
        except (KeyError, TypeError) as error:
            raise LayoutChangedError(
                "Digikala Jet search response no longer contains data.result/pager"
            ) from error
        products = tuple(self.parse_product(item) for item in results)
        current = int(pager.get("current_page", page))
        total_pages = int(pager.get("total_pages", current))
        return SearchPage(
            products,
            page=current,
            has_next=current < total_pages,
            total=parse_int(pager.get("total_items")),
            next_page=current + 1 if current < total_pages else None,
        )

    async def get_product(self, identifier_or_url: str) -> Product:
        match = _COMPOSITE_ID.search(identifier_or_url)
        if not match:
            raise ValueError(
                "Digikala Jet identifiers must be 'shop_id:product_id' from search results"
            )
        shop_id, product_id = match.groups()
        if not shop_id:
            raise ValueError(
                "Digikala Jet product IDs are shop-specific; pass the composite identifier "
                "returned by search, such as '185113440676:22122708'"
            )
        params = urlencode({"latitude": self.latitude, "longitude": self.longitude})
        payload = await self._get_json(
            f"{self.api_url}/shop/{shop_id}/product/{product_id}/?{params}"
        )
        try:
            return self.parse_product(payload["data"]["product"])
        except (KeyError, TypeError) as error:
            raise LayoutChangedError(
                "Digikala Jet detail response no longer contains data.product"
            ) from error

    async def _get_json(self, url: str) -> dict[str, Any]:
        await self.session.start()

        async def operation() -> APIResponse:
            return await self.session.context.request.get(
                url, timeout=self.config.navigation_timeout_ms
            )

        response = await self.session.run(operation, operation_name="api_get", url=url)
        payload: object = await response.json()
        if not isinstance(payload, dict):
            raise LayoutChangedError("Digikala Jet returned non-object JSON")
        if payload.get("status") == 404:
            raise ProductNotFoundError(f"Digikala Jet resource not found: {url}")
        return payload

    @classmethod
    def parse_product(cls, data: Mapping[str, Any]) -> Product:
        product_id = data.get("id")
        title = normalize_text(data.get("title"))
        shop = data.get("shop")
        shop = shop if isinstance(shop, dict) else {}
        shop_id = shop.get("id")
        if product_id is None or shop_id is None or not title:
            raise LayoutChangedError("Digikala Jet product is missing id, shop.id, or title")
        price = data.get("price")
        price = price if isinstance(price, dict) else {}
        stock = data.get("stock")
        stock = stock if isinstance(stock, dict) else {}
        identifier = f"{shop_id}:{product_id}"
        return Product(
            shop=cls.shop_name,
            identifier=identifier,
            title=title,
            url=f"{cls.base_url}/search/?q={product_id}&shopId={shop_id}",
            image_url=normalize_text(data.get("media")),
            current_price=normalize_price(price.get("price"), source_currency="IRR"),
            original_price=normalize_price(price.get("aggregated_price"), source_currency="IRR"),
            discount_percentage=price.get("discount_percentage"),
            currency="IRT",
            availability=(
                Availability.IN_STOCK if stock.get("has_stock") else Availability.OUT_OF_STOCK
            ),
            seller=normalize_text(shop.get("title")),
            popularity="best_deal"
            if isinstance(data.get("badges"), dict) and data["badges"].get("is_best_deal")
            else None,
            metadata={
                "merchant_product_id": data.get("merchant_product_id"),
                "category": (data.get("category") or {}).get("title"),
            },
        )
