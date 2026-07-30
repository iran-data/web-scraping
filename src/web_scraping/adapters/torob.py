"""Torob adapter using the first-party JSON consumed by its web client."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar
from urllib.parse import urlencode

from playwright.async_api import APIResponse

from web_scraping.adapters.base import BaseShopAdapter
from web_scraping.exceptions import LayoutChangedError, ProductNotFoundError
from web_scraping.models import Availability, Product, SearchPage, SortOption
from web_scraping.normalization import absolute_url, normalize_price, normalize_text, parse_int

_KEY_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f-]{27,})", re.IGNORECASE)


class TorobAdapter(BaseShopAdapter):
    shop_name = "torob"
    base_url = "https://torob.com"
    api_url = "https://api.torob.com/v4/base-product"
    page_size = 24
    sort_values: ClassVar[dict[SortOption, str]] = {
        SortOption.RELEVANCE: "popularity",
        SortOption.MOST_POPULAR: "popularity",
        SortOption.BEST_SELLING: "popularity",
        SortOption.CHEAPEST: "price",
        SortOption.MOST_EXPENSIVE: "-price",
        SortOption.NEWEST: "-date",
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
            ("page", page - 1),
            ("size", self.page_size),
            ("sort", self.sort_values[sort]),
            ("query", keyword),
        ]
        for key, value in (filters or {}).items():
            if isinstance(value, Sequence) and not isinstance(value, str):
                params.extend((key, item) for item in value)
            else:
                params.append((key, value))
        payload = await self._get_json(f"{self.api_url}/search/?{urlencode(params, doseq=True)}")
        results = payload.get("results")
        if not isinstance(results, list):
            raise LayoutChangedError("Torob search response has no results list")
        products = tuple(self.parse_product(item) for item in results)
        total = parse_int(payload.get("count"))
        has_next = bool(payload.get("next"))
        return SearchPage(
            products,
            page=page,
            has_next=has_next,
            total=total,
            next_page=page + 1 if has_next else None,
        )

    async def get_product(self, identifier_or_url: str) -> Product:
        match = _KEY_RE.search(identifier_or_url)
        if not match:
            raise ValueError(f"Invalid Torob product identifier: {identifier_or_url!r}")
        key = match.group(1)
        payload = await self._get_json(f"{self.api_url}/details/?{urlencode({'prk': key})}")
        return self.parse_product(payload, detail=True)

    async def _get_json(self, url: str) -> dict[str, Any]:
        await self.session.start()

        async def operation() -> APIResponse:
            return await self.session.context.request.get(
                url, timeout=self.config.navigation_timeout_ms
            )

        response = await self.session.run(operation, operation_name="api_get", url=url)
        payload: object = await response.json()
        if not isinstance(payload, dict):
            raise LayoutChangedError("Torob returned non-object JSON")
        if response.status == 404:
            raise ProductNotFoundError(f"Torob resource not found: {url}")
        return payload

    @classmethod
    def parse_product(cls, data: Mapping[str, Any], *, detail: bool = False) -> Product:
        identifier = normalize_text(data.get("random_key"))
        title = normalize_text(data.get("name1"))
        if not identifier or not title:
            raise LayoutChangedError("Torob product is missing random_key or name1")
        seller = None
        availability = Availability.UNKNOWN
        if detail:
            products_info = data.get("products_info")
            products_info = products_info if isinstance(products_info, dict) else {}
            offers = products_info.get("result")
            offers = (
                [offer for offer in offers if isinstance(offer, dict)]
                if isinstance(offers, list)
                else []
            )
            available_offers = [offer for offer in offers if offer.get("availability")]
            selected = min(
                available_offers,
                key=lambda offer: offer.get("price") or float("inf"),
                default=None,
            )
            if selected:
                seller = normalize_text(selected.get("shop_name"))
                availability = Availability.IN_STOCK
        elif data.get("price") is not None:
            availability = Availability.IN_STOCK
        return Product(
            shop=cls.shop_name,
            identifier=identifier,
            title=title,
            url=absolute_url(cls.base_url, data.get("web_client_absolute_url"))
            or f"{cls.base_url}/p/{identifier}/",
            image_url=normalize_text(data.get("image_url")),
            current_price=normalize_price(data.get("price"), source_currency="IRT"),
            currency="IRT",
            availability=availability,
            seller=seller,
            popularity=normalize_text(data.get("shop_text") or data.get("estimated_sell")),
            metadata={
                "english_title": data.get("name2"),
                "shop_count": len(
                    (data.get("products_info") or {}).get("result", [])
                    if isinstance(data.get("products_info"), dict)
                    else []
                ),
            },
        )
