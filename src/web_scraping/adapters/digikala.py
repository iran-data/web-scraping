"""Digikala adapter using the JSON endpoints observed from its web application."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlencode

from playwright.async_api import APIResponse

from web_scraping.adapters.base import BaseShopAdapter
from web_scraping.exceptions import (
    BotChallengeError,
    LayoutChangedError,
    ProductNotFoundError,
)
from web_scraping.models import Availability, Product, SearchPage, SortOption
from web_scraping.normalization import (
    absolute_url,
    normalize_price,
    normalize_rating,
    normalize_text,
)

_PRODUCT_ID_RE = re.compile(r"(?:dkp-)?(\d+)")
_SORT_IDS = {
    SortOption.RELEVANCE: 22,
    SortOption.NEWEST: 1,
    SortOption.CHEAPEST: 20,
    SortOption.MOST_EXPENSIVE: 21,
    SortOption.MOST_POPULAR: 4,
    SortOption.BEST_SELLING: 7,
}


class DigikalaAdapter(BaseShopAdapter):
    shop_name = "digikala"
    base_url = "https://www.digikala.com"
    api_url = "https://api.digikala.com"

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
            ("page", page),
            ("sort", _SORT_IDS[sort]),
        ]
        for key, value in (filters or {}).items():
            if isinstance(value, Sequence) and not isinstance(value, str):
                params.extend((key, item) for item in value)
            else:
                params.append((key, value))
        url = f"{self.api_url}/discovery/api/v2/search?{urlencode(params, doseq=True)}"
        payload = await self._get_json(url)
        try:
            listing = payload["data"]["widgets"][0]["data"]
            product_widgets = listing["widgets"]
            pager = listing["pager"]
        except (KeyError, IndexError, TypeError) as error:
            raise LayoutChangedError(
                "Digikala search response no longer contains data.widgets[0].data.widgets/pager"
            ) from error
        products = tuple(
            self.parse_product(widget["data"])
            for widget in product_widgets
            if widget.get("type") == "product" and isinstance(widget.get("data"), dict)
        )
        if product_widgets and not products:
            raise LayoutChangedError("Digikala search returned widgets but no product widgets")
        current_page = int(pager.get("current_page", page))
        total_pages = int(pager.get("total_pages", current_page))
        return SearchPage(
            items=products,
            page=current_page,
            has_next=current_page < total_pages,
            total=pager.get("total_items"),
            next_page=current_page + 1 if current_page < total_pages else None,
        )

    async def get_product(self, identifier_or_url: str) -> Product:
        match = _PRODUCT_ID_RE.search(identifier_or_url)
        if not match:
            raise ValueError(
                f"Could not find a Digikala product identifier in {identifier_or_url!r}"
            )
        identifier = match.group(1)
        payload = await self._get_json(f"{self.api_url}/v2/product/{identifier}/")
        try:
            data = payload["data"]["product"]
        except (KeyError, TypeError) as error:
            raise LayoutChangedError(
                "Digikala detail response no longer contains data.product"
            ) from error
        return self.parse_product(data)

    async def _get_json(self, url: str) -> dict[str, Any]:
        await self.session.start()

        async def operation() -> APIResponse:
            return await self.session.context.request.get(
                url, timeout=self.config.navigation_timeout_ms
            )

        response = await self.session.run(operation, operation_name="api_get", url=url)
        if response.status == 404:
            raise ProductNotFoundError(f"Digikala resource not found: {url}")
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type:
            body = (await response.text()).lower()
            if any(marker in body for marker in ("captcha", "cloudflare", "access denied")):
                raise BotChallengeError("Digikala returned a bot challenge instead of JSON")
            raise LayoutChangedError(
                f"Digikala endpoint returned {content_type or 'an unknown content type'}"
            )
        payload: object = await response.json()
        if not isinstance(payload, dict):
            raise LayoutChangedError("Digikala endpoint returned a non-object JSON response")
        return payload

    @classmethod
    def parse_product(cls, data: Mapping[str, Any]) -> Product:
        try:
            identifier = str(data["id"])
            title = normalize_text(str(data["title_fa"]))
            url_data = data["url"]
        except (KeyError, TypeError) as error:
            raise LayoutChangedError(
                "Digikala product is missing required id, title_fa, or url fields"
            ) from error
        if not title:
            raise LayoutChangedError("Digikala product title is empty")
        url_value = url_data.get("uri") if isinstance(url_data, dict) else str(url_data)
        url = absolute_url(cls.base_url, url_value)
        if not url:
            raise LayoutChangedError("Digikala product URL is empty")

        variant = data.get("default_variant")
        variant = variant if isinstance(variant, dict) else {}
        price = variant.get("price")
        price = price if isinstance(price, dict) else {}
        images = data.get("images")
        images = images if isinstance(images, dict) else {}
        main_image = images.get("main")
        main_image = main_image if isinstance(main_image, dict) else {}
        image_urls = main_image.get("url") or main_image.get("webp_url") or []
        rating = data.get("rating")
        rating = rating if isinstance(rating, dict) else {}
        seller = variant.get("seller")
        seller = seller if isinstance(seller, dict) else {}
        brand = data.get("brand")
        brand = brand if isinstance(brand, dict) else {}
        status = str(variant.get("status") or data.get("status") or "")

        selling_price = price.get("selling_price")
        original_price = price.get("rrp_price")
        return Product(
            shop=cls.shop_name,
            identifier=identifier,
            title=title,
            url=url,
            image_url=absolute_url(cls.base_url, image_urls[0]) if image_urls else None,
            current_price=normalize_price(selling_price, source_currency="IRR"),
            original_price=normalize_price(original_price, source_currency="IRR"),
            discount_percentage=price.get("discount_percent"),
            currency="IRT",
            availability=(
                Availability.IN_STOCK
                if status == "marketable"
                else Availability.OUT_OF_STOCK
                if status in {"out_of_stock", "unmarketable"}
                else Availability.UNKNOWN
            ),
            seller=normalize_text(seller.get("title")),
            brand=normalize_text(brand.get("title_fa") or data.get("data_layer", {}).get("brand")),
            rating=normalize_rating(rating.get("rate"), source_max=100),
            review_count=rating.get("count") or data.get("comments_count"),
            popularity=None,
            metadata={"variant_id": variant.get("id")},
        )
