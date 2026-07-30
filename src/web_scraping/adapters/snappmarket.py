"""Central-Tehran Snapp Market adapter."""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar
from urllib.parse import urlencode

from playwright.async_api import APIResponse

from web_scraping.adapters.base import BaseShopAdapter
from web_scraping.exceptions import (
    LayoutChangedError,
    ProductNotFoundError,
    UnsupportedFeatureError,
)
from web_scraping.models import Availability, Product, SearchPage, SortOption
from web_scraping.normalization import normalize_price, normalize_text, parse_int

_ID_RE = re.compile(r"(\d+)")


class SnappMarketAdapter(BaseShopAdapter):
    shop_name = "snappmarket"
    base_url = "https://snapp.market"
    api_url = "https://svc.snapp.market"
    latitude = 35.7005
    longitude = 51.3917
    page_size = 10
    supported_sorts: ClassVar[frozenset[SortOption]] = frozenset({SortOption.RELEVANCE})

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._udid = str(uuid.uuid4())

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
        if sort not in self.supported_sorts:
            raise UnsupportedFeatureError(
                f"Snapp Market does not expose a verified {sort.value!r} search sort"
            )
        params: list[tuple[str, object]] = [
            ("page", page - 1),
            ("query", keyword),
            ("new_search", 1),
            ("new_design", 0),
            ("superType[]", 4),
            ("size", self.page_size),
            ("source", 2),
        ]
        for key, value in (filters or {}).items():
            if isinstance(value, Sequence) and not isinstance(value, str):
                params.extend((key, item) for item in value)
            else:
                params.append((key, value))
        payload = await self._get_json(
            f"{self.api_url}/mobile/v3/product-vendors/search?"
            f"{urlencode(params, doseq=True)}&{self._client_params()}"
        )
        items = payload.get("items")
        if not isinstance(items, list):
            raise LayoutChangedError("Snapp Market search response has no items list")
        products = tuple(self.parse_search_product(item) for item in items)
        total = parse_int(payload.get("total")) or len(products)
        has_next = page * self.page_size < total
        return SearchPage(
            products,
            page=page,
            has_next=has_next,
            total=total,
            next_page=page + 1 if has_next else None,
        )

    async def get_product(self, identifier_or_url: str) -> Product:
        match = _ID_RE.search(identifier_or_url)
        if not match:
            raise ValueError(f"Invalid Snapp Market product identifier: {identifier_or_url!r}")
        identifier = match.group(1)
        payload = await self._get_json(
            f"{self.api_url}/express-search/v1/pb/products/{identifier}?{self._client_params()}"
        )
        return self.parse_product_payload(payload)

    def _client_params(self) -> str:
        return urlencode(
            {
                "client": "PWA",
                "deviceType": "PWA",
                "appVersion": "1.397.48",
                "UDID": self._udid,
                "lat": f"{self.latitude:.6f}",
                "long": f"{self.longitude:.6f}",
            }
        )

    async def _get_json(self, url: str) -> dict[str, Any]:
        await self.session.start()

        async def operation() -> APIResponse:
            return await self.session.context.request.get(
                url, timeout=self.config.navigation_timeout_ms
            )

        response = await self.session.run(operation, operation_name="api_get", url=url)
        payload: object = await response.json()
        if not isinstance(payload, dict):
            raise LayoutChangedError("Snapp Market returned non-object JSON")
        if response.status == 404 or payload.get("code") == 404:
            raise ProductNotFoundError(f"Snapp Market resource not found: {url}")
        return payload

    @classmethod
    def parse_search_product(cls, data: Mapping[str, Any]) -> Product:
        identifier = data.get("id")
        title = normalize_text(data.get("title"))
        if identifier is None or not title:
            raise LayoutChangedError("Snapp Market product is missing id or title")
        original = normalize_price(data.get("price"), source_currency="IRT")
        discount = normalize_price(data.get("discount"), source_currency="IRT") or 0
        current = original - discount if original is not None else None
        images = data.get("images")
        first_image = images[0] if isinstance(images, list) and images else {}
        return Product(
            shop=cls.shop_name,
            identifier=str(identifier),
            title=title,
            url=f"{cls.base_url}/product/{identifier}",
            image_url=normalize_text(
                first_image.get("main") if isinstance(first_image, dict) else None
            ),
            current_price=current,
            original_price=original,
            discount_percentage=data.get("discountRatio"),
            currency="IRT",
            availability=Availability.IN_STOCK,
        )

    @classmethod
    def parse_product_payload(cls, data: Mapping[str, Any]) -> Product:
        identifier = data.get("id")
        title = normalize_text(data.get("title"))
        if identifier is None or not title:
            raise LayoutChangedError("Snapp Market detail is missing id or title")
        price = normalize_price(data.get("min_price"), source_currency="IRT")
        discount = normalize_price(data.get("discount"), source_currency="IRT") or 0
        images = data.get("images")
        first_image = images[0] if isinstance(images, list) and images else {}
        return Product(
            shop=cls.shop_name,
            identifier=str(identifier),
            title=title,
            url=f"{cls.base_url}/product/{identifier}",
            image_url=normalize_text(
                first_image.get("main") if isinstance(first_image, dict) else None
            ),
            current_price=price - discount if price is not None else None,
            original_price=price,
            discount_percentage=data.get("discount_ratio"),
            currency="IRT",
            availability=Availability.IN_STOCK,
            brand=normalize_text(data.get("brand_title")),
            metadata={
                "category": data.get("category_title"),
                "subcategory": data.get("subcategory_title"),
            },
        )
