"""Reusable semantic-page adapter for shops without a stable public JSON endpoint."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any, ClassVar
from urllib.parse import urlencode, urlparse

from web_scraping.adapters.base import BaseShopAdapter
from web_scraping.adapters.parser import json_ld_products, load_json
from web_scraping.exceptions import LayoutChangedError, ProductNotFoundError
from web_scraping.models import Availability, Product, SearchPage, SortOption
from web_scraping.normalization import (
    absolute_url,
    normalize_price,
    normalize_rating,
    normalize_text,
    parse_int,
    parse_number,
)

_ID_RE = re.compile(r"(\d+)")


class StructuredPageAdapter(BaseShopAdapter):
    """Fallback based on schema.org Product and semantic product links."""

    search_path = "/search"
    search_query_key = "q"
    page_query_key = "page"
    product_link_fragment = "/product"
    source_currency = "IRT"
    sort_values: ClassVar[Mapping[SortOption, str]] = {}

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
            (self.search_query_key, keyword),
            (self.page_query_key, page),
        ]
        if sort in self.sort_values:
            params.append(("sort", self.sort_values[sort]))
        for key, value in (filters or {}).items():
            if isinstance(value, Sequence) and not isinstance(value, str):
                params.extend((key, item) for item in value)
            else:
                params.append((key, value))
        url = f"{self.base_url}{self.search_path}?{urlencode(params, doseq=True)}"
        browser_page = await self.session.new_page()
        try:
            await self.session.navigate(browser_page, url)
            data = await browser_page.locator(
                f'a[href*="{self.product_link_fragment}"]'
            ).evaluate_all(
                """(nodes) => nodes.map(node => {
                    const card = node.closest('article, li, [data-testid], [class*="product"]')
                        || node;
                    const image = card.querySelector('img');
                    return {
                        href: node.href,
                        title: image?.alt || node.getAttribute('title')
                            || card.querySelector('h2,h3')?.textContent || node.textContent,
                        image: image?.currentSrc || image?.src || null,
                        text: card.textContent || '',
                    };
                })"""
            )
            unique: dict[str, Product] = {}
            for card in data:
                product = self._parse_card(card)
                if product is not None:
                    unique[product.url] = product
            if not unique:
                body = normalize_text(await browser_page.locator("body").inner_text()) or ""
                if any(marker in body for marker in ("یافت نشد", "نتیجه‌ای یافت نشد")):
                    return SearchPage((), page=page, has_next=False, total=0)
                raise LayoutChangedError(
                    f"{self.shop_name} search page contained no recognizable product cards"
                )
            next_locator = browser_page.locator(
                'a[rel="next"], [aria-label*="next" i], [aria-label*="بعد"]'
            )
            has_next = await next_locator.count() > 0
            return SearchPage(
                tuple(unique.values()),
                page=page,
                has_next=has_next,
                next_page=page + 1 if has_next else None,
            )
        finally:
            await browser_page.close()

    async def get_product(self, identifier_or_url: str) -> Product:
        if identifier_or_url.startswith(("http://", "https://")):
            url = identifier_or_url
        else:
            url = self.product_url(identifier_or_url)
        browser_page = await self.session.new_page()
        try:
            await self.session.navigate(browser_page, url)
            scripts = await browser_page.locator(
                'script[type="application/ld+json"]'
            ).all_text_contents()
            candidates: list[dict[str, Any]] = []
            for index, text in enumerate(scripts):
                candidates.extend(
                    json_ld_products(load_json(text, source=f"JSON-LD script {index}"))
                )
            if not candidates:
                if await browser_page.locator("body").inner_text() == "":
                    raise ProductNotFoundError(f"{self.shop_name} product not found: {url}")
                raise LayoutChangedError(
                    f"{self.shop_name} detail page has no schema.org Product data"
                )
            return self._parse_json_ld(candidates[0], fallback_url=browser_page.url)
        finally:
            await browser_page.close()

    def product_url(self, identifier: str) -> str:
        raise ValueError(
            f"{self.shop_name} requires a product URL; bare identifiers are not stable on this site"
        )

    def _parse_card(self, card: Mapping[str, Any]) -> Product | None:
        url = absolute_url(self.base_url, card.get("href"))
        title = normalize_text(card.get("title"))
        if not url or not title:
            return None
        identifier = self.identifier_from_url(url)
        text = normalize_text(card.get("text")) or ""
        prices: list[Decimal] = []
        for match in re.findall(r"\d[\d٬,.\s]{2,}", text):
            price = normalize_price(match, source_currency=self.source_currency)
            if price is not None and price >= 100:
                prices.append(price)
        current = prices[0] if prices else None
        original = (
            prices[1] if current is not None and len(prices) > 1 and prices[1] >= current else None
        )
        return Product(
            shop=self.shop_name,
            identifier=identifier,
            title=title,
            url=url,
            image_url=absolute_url(self.base_url, card.get("image")),
            current_price=current,
            original_price=original,
            currency="IRT",
            availability=(Availability.OUT_OF_STOCK if "ناموجود" in text else Availability.UNKNOWN),
        )

    def _parse_json_ld(self, data: Mapping[str, Any], *, fallback_url: str) -> Product:
        title = normalize_text(data.get("name"))
        url = absolute_url(self.base_url, data.get("url")) or fallback_url
        if not title:
            raise LayoutChangedError(f"{self.shop_name} Product JSON-LD has no name")
        offers = data.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        aggregate = data.get("aggregateRating") or {}
        image = data.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        brand = data.get("brand")
        if isinstance(brand, dict):
            brand = brand.get("name")
        availability = str(offers.get("availability", "")).lower()
        price_currency = str(offers.get("priceCurrency", self.source_currency))
        source_currency = "IRT" if price_currency.upper() in {"IRT", "TOMAN"} else "IRR"
        return Product(
            shop=self.shop_name,
            identifier=str(
                data.get("sku") or data.get("productID") or self.identifier_from_url(url)
            ),
            title=title,
            url=url,
            image_url=absolute_url(self.base_url, image),
            current_price=normalize_price(offers.get("price"), source_currency=source_currency),
            original_price=normalize_price(
                offers.get("highPrice"), source_currency=source_currency
            ),
            currency="IRT",
            availability=(
                Availability.IN_STOCK
                if "instock" in availability
                else Availability.OUT_OF_STOCK
                if "outofstock" in availability
                else Availability.UNKNOWN
            ),
            seller=normalize_text(
                offers.get("seller", {}).get("name")
                if isinstance(offers.get("seller"), dict)
                else offers.get("seller")
            ),
            brand=normalize_text(brand),
            rating=normalize_rating(aggregate.get("ratingValue")),
            review_count=parse_int(aggregate.get("reviewCount") or aggregate.get("ratingCount")),
            discount_percentage=self._discount(offers.get("price"), offers.get("highPrice")),
        )

    @staticmethod
    def identifier_from_url(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        matches = _ID_RE.findall(path)
        return matches[-1] if matches else path.rsplit("/", 1)[-1]

    @staticmethod
    def _discount(current: object, original: object) -> Decimal | None:
        current_value, original_value = parse_number(current), parse_number(original)
        if not current_value or not original_value or original_value <= current_value:
            return None
        return ((original_value - current_value) * 100 / original_value).quantize(Decimal("0.01"))
