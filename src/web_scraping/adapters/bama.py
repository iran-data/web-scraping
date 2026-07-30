"""Bama vehicle-listing adapter."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlencode, urlparse

from playwright.async_api import APIResponse

from web_scraping.adapters.base import BaseShopAdapter
from web_scraping.adapters.parser import json_ld_products, load_json
from web_scraping.exceptions import (
    LayoutChangedError,
    UnsupportedFeatureError,
)
from web_scraping.models import (
    Availability,
    CarPrice,
    CarPricePage,
    CarPriceType,
    Product,
    SearchPage,
    SortOption,
)
from web_scraping.normalization import (
    absolute_url,
    normalize_price,
    normalize_text,
    parse_int,
    parse_number,
)
from web_scraping.sources import SourceCapability

_DETAIL_ID_RE = re.compile(r"detail-([a-zA-Z0-9]+)")
_YEAR_RE = re.compile(r"^(?:13|14|19|20)\d{2}$")
_PRICE_RE = re.compile(
    r"([\d\u06f0-\u06f9\u0660-\u0669][\d\u06f0-\u06f9\u0660-\u0669٬,.\s]*)\s*تومان"
)
_MILEAGE_RE = re.compile(r"کارکرد\s+([\d\u06f0-\u06f9\u0660-\u0669٬,]+)")
_PRICE_TYPE_QUERY = {
    CarPriceType.MARKET: "MarketPrice",
    CarPriceType.FACTORY: "FactoryPrice",
    CarPriceType.AGENCY: "AgencyPrice",
}
_PRICE_TYPE_RESPONSE = {value: key for key, value in _PRICE_TYPE_QUERY.items()}


class BamaAdapter(BaseShopAdapter):
    """Scrape public Bama vehicle advertisements using rendered semantic links."""

    shop_name = "bama"
    base_url = "https://bama.ir"
    capabilities = BaseShopAdapter.capabilities | {SourceCapability.REFERENCE_PRICES}

    async def car_prices(
        self,
        keyword: str = "",
        *,
        page: int = 1,
        page_size: int = 20,
        price_type: CarPriceType | None = None,
    ) -> CarPricePage:
        """Return Bama's reference prices for new vehicles."""
        if page < 1:
            raise ValueError("page must be at least 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")
        params: dict[str, object] = {
            "pageIndex": page - 1,
            "pageSize": page_size,
        }
        if keyword:
            params["searchQuery"] = keyword
        if price_type is not None:
            params["priceType"] = _PRICE_TYPE_QUERY[price_type]
        payload = await self._get_json(
            f"{self.base_url}/cad/api/price/hierarchy?{urlencode(params)}"
        )
        groups = payload.get("data")
        if not isinstance(groups, list):
            raise LayoutChangedError("Bama price response has no data list")
        items: list[CarPrice] = []
        has_more = False
        for group in groups:
            if not isinstance(group, Mapping):
                raise LayoutChangedError("Bama price response contains an invalid group")
            values = group.get("items")
            if not isinstance(values, list):
                raise LayoutChangedError("Bama price group has no items list")
            items.extend(self.parse_car_price(value) for value in values)
            count = parse_int(group.get("items_count"))
            has_more = has_more or (count is not None and count > len(values))
        # A full group page means another group page may be available.
        has_next = has_more or len(groups) >= page_size
        metadata = payload.get("metadata")
        return CarPricePage(
            tuple(items),
            page=page,
            has_next=has_next,
            next_page=page + 1 if has_next else None,
            last_updated=normalize_text(
                metadata.get("last_update") if isinstance(metadata, Mapping) else None
            ),
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
            raise LayoutChangedError("Bama returned non-object JSON")
        return payload

    @classmethod
    def parse_car_price(cls, data: Mapping[str, Any]) -> CarPrice:
        identifier = data.get("car_price_id")
        brand = normalize_text(data.get("brand_fa"))
        model = normalize_text(data.get("model_fa"))
        price = normalize_price(data.get("price"), source_currency="IRT")
        type_value = data.get("price_type")
        raw_type = type_value.get("value") if isinstance(type_value, Mapping) else None
        price_type = _PRICE_TYPE_RESPONSE.get(str(raw_type))
        if identifier is None or not brand or not model or price is None or price_type is None:
            raise LayoutChangedError(
                "Bama car price is missing ID, vehicle name, price, or price type"
            )
        company_value = data.get("company")
        manufacture_value = data.get("manufacture_type")
        slug = "_".join(
            part
            for part in (
                normalize_text(data.get("brand")),
                normalize_text(data.get("model")),
                normalize_text(data.get("trim")),
            )
            if part
        )
        return CarPrice(
            identifier=str(identifier),
            brand=brand,
            model=model,
            trim=normalize_text(data.get("trim_fa")),
            year=parse_int(data.get("model_year")),
            price=price,
            price_type=price_type,
            price_change_percentage=parse_number(data.get("price_diff")),
            price_date=normalize_text(data.get("price_date")),
            company=normalize_text(
                company_value.get("display_name") if isinstance(company_value, Mapping) else None
            ),
            manufacture_type=normalize_text(
                manufacture_value.get("display_name")
                if isinstance(manufacture_value, Mapping)
                else None
            ),
            url=f"{cls.base_url}/price/{slug}" if slug else None,
        )

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
        if page > 1:
            raise UnsupportedFeatureError(
                "Bama listing pagination uses an unverified infinite-scroll contract"
            )
        if sort != SortOption.RELEVANCE:
            raise UnsupportedFeatureError(
                f"Bama does not expose a verified {sort.value!r} listing sort"
            )
        params: list[tuple[str, object]] = [("page", page)]
        for key, value in (filters or {}).items():
            if isinstance(value, Sequence) and not isinstance(value, str):
                params.extend((key, item) for item in value)
            else:
                params.append((key, value))
        url = f"{self.base_url}/car?{urlencode(params, doseq=True)}"
        browser_page = await self.session.new_page()
        try:
            await self.session.navigate(browser_page, url)
            cards: list[dict[str, Any]] = await browser_page.locator(
                'a[href*="/car/detail-"]'
            ).evaluate_all(
                """nodes => nodes.map(node => ({
                    href: node.href,
                    text: node.innerText || node.textContent || '',
                    image: node.querySelector('img')?.currentSrc
                        || node.querySelector('img')?.src || null
                }))"""
            )
            products = [self.parse_card(card) for card in cards]
            needle = normalize_text(keyword)
            if needle:
                products = [item for item in products if needle in item.title]
            unique = {item.identifier: item for item in products}
            if not cards:
                raise LayoutChangedError("Bama search page has no vehicle advertisement links")
            has_next = (
                await browser_page.locator(
                    'a[rel="next"], a[aria-label*="بعد"], button[aria-label*="بعد"]'
                ).count()
                > 0
            )
            return SearchPage(
                tuple(unique.values()),
                page=page,
                has_next=has_next,
                next_page=page + 1 if has_next else None,
            )
        finally:
            await browser_page.close()

    async def get_product(self, identifier_or_url: str) -> Product:
        url = (
            identifier_or_url
            if identifier_or_url.startswith(("http://", "https://"))
            else f"{self.base_url}/car/detail-{identifier_or_url}"
        )
        browser_page = await self.session.new_page()
        try:
            await self.session.navigate(browser_page, url)
            scripts = await browser_page.locator(
                'script[type="application/ld+json"]'
            ).all_text_contents()
            for index, text in enumerate(scripts):
                products = json_ld_products(load_json(text, source=f"Bama JSON-LD script {index}"))
                if products:
                    return self.parse_detail(products[0], fallback_url=browser_page.url)
            raise LayoutChangedError("Bama detail page has no schema.org Product data")
        finally:
            await browser_page.close()

    @classmethod
    def parse_card(cls, card: Mapping[str, Any]) -> Product:
        url = absolute_url(cls.base_url, card.get("href"))
        raw_text = card.get("text")
        if not url or not isinstance(raw_text, str) or not raw_text.strip():
            raise LayoutChangedError("Bama listing card is missing its URL or text")
        identifier = cls.identifier_from_url(url)
        lines = [
            normalized for line in raw_text.splitlines() if (normalized := normalize_text(line))
        ]
        year_index = next(
            (index for index, line in enumerate(lines) if _YEAR_RE.fullmatch(line)),
            None,
        )
        if year_index is None:
            raise LayoutChangedError("Bama listing card has no recognizable vehicle year")
        title_parts = [line for line in lines[:year_index] if not line.isdigit()]
        title = normalize_text(" ".join(title_parts))
        if not title:
            raise LayoutChangedError("Bama listing card has no recognizable title")
        prices = _PRICE_RE.findall(raw_text)
        mileage_match = _MILEAGE_RE.search(raw_text)
        return Product(
            shop=cls.shop_name,
            identifier=identifier,
            title=f"{title} {lines[year_index]}",
            url=url,
            image_url=absolute_url(cls.base_url, card.get("image")),
            current_price=normalize_price(prices[0], source_currency="IRT") if prices else None,
            currency="IRT",
            availability=Availability.IN_STOCK,
            metadata={
                "year": parse_int(lines[year_index]),
                "mileage_km": parse_int(mileage_match.group(1)) if mileage_match else None,
            },
        )

    @classmethod
    def parse_detail(cls, data: Mapping[str, Any], *, fallback_url: str) -> Product:
        name = normalize_text(data.get("name"))
        offered = data.get("offers")
        offers = offered if isinstance(offered, Mapping) else {}
        item_value = offers.get("itemOffered")
        item = item_value if isinstance(item_value, Mapping) else {}
        url = absolute_url(cls.base_url, data.get("url")) or fallback_url
        identifier = normalize_text(item.get("identifier")) or cls.identifier_from_url(url)
        if not name or not identifier:
            raise LayoutChangedError("Bama Product JSON-LD is missing name or identifier")
        brand_value = data.get("brand")
        brand = brand_value.get("name") if isinstance(brand_value, Mapping) else brand_value
        availability = str(offers.get("availability", "")).lower()
        return Product(
            shop=cls.shop_name,
            identifier=identifier,
            title=name,
            url=url,
            image_url=absolute_url(cls.base_url, data.get("image")),
            # Bama labels this IRR in JSON-LD, but the rendered amount is explicitly toman.
            current_price=normalize_price(offers.get("price"), source_currency="IRT"),
            currency="IRT",
            availability=(
                Availability.IN_STOCK if "instock" in availability else Availability.UNKNOWN
            ),
            brand=normalize_text(brand),
            metadata={
                "year": parse_int(item.get("vehicleModelDate")),
                "mileage_km": parse_int(
                    item.get("mileageFromOdometer", {}).get("Value")
                    if isinstance(item.get("mileageFromOdometer"), Mapping)
                    else None
                ),
                "transmission": normalize_text(item.get("vehicleTransmission")),
                "color": normalize_text(data.get("color")),
            },
        )

    @staticmethod
    def identifier_from_url(url: str) -> str:
        match = _DETAIL_ID_RE.search(urlparse(url).path)
        if not match:
            raise LayoutChangedError(f"Unrecognized Bama detail URL: {url}")
        return match.group(1)
