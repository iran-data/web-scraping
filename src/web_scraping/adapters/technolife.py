"""Technolife adapter based on its server-rendered Next.js data."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar
from urllib.parse import urlencode

from web_scraping.adapters.structured import StructuredPageAdapter
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

_CODE_RE = re.compile(r"(?:TLP-)?(\d+)")


class TechnolifeAdapter(StructuredPageAdapter):
    shop_name = "technolife"
    base_url = "https://www.technolife.com"
    search_path = "/product/list/search"
    search_query_key = "keywords"
    product_link_fragment = "/product-"
    page_size = 30
    sort_values: ClassVar[dict[SortOption, str]] = {
        SortOption.RELEVANCE: "",
        SortOption.BEST_SELLING: "order-desc",
        SortOption.MOST_POPULAR: "order-desc",
        SortOption.CHEAPEST: "price-asc",
        SortOption.MOST_EXPENSIVE: "price-desc",
        SortOption.NEWEST: "date-desc",
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
        params: list[tuple[str, object]] = [("keywords", keyword)]
        if page > 1:
            params.append(("page", page))
        ordering = self.sort_values[sort]
        if ordering:
            params.append(("ordering", ordering))
        for key, value in (filters or {}).items():
            if isinstance(value, Sequence) and not isinstance(value, str):
                params.extend((key, item) for item in value)
            else:
                params.append((key, value))
        url = f"{self.base_url}{self.search_path}?{urlencode(params, doseq=True)}"

        browser_page = await self.session.new_page()
        try:
            await self.session.navigate(browser_page, url)
            next_data = await browser_page.locator("script#__NEXT_DATA__").text_content()
            if not next_data:
                raise LayoutChangedError("Technolife search page has no __NEXT_DATA__ script")
            try:
                payload = json.loads(next_data)
            except json.JSONDecodeError as error:
                raise LayoutChangedError("Technolife __NEXT_DATA__ is invalid JSON") from error
            return self.parse_search_payload(payload, requested_page=page)
        finally:
            await browser_page.close()

    async def get_product(self, identifier_or_url: str) -> Product:
        url = (
            identifier_or_url
            if identifier_or_url.startswith(("http://", "https://"))
            else self.product_url(identifier_or_url)
        )
        browser_page = await self.session.new_page()
        try:
            await self.session.navigate(browser_page, url)
            scripts = await browser_page.locator(
                'script[type="application/ld+json"]'
            ).all_text_contents()
            for text in scripts:
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict) and data.get("@type") == "Product":
                    return self.parse_product_payload(data, fallback_url=browser_page.url)
            body = await browser_page.locator("body").inner_text()
            if "یافت نشد" in body or "404" in await browser_page.title():
                raise ProductNotFoundError(f"Technolife product not found: {url}")
            raise LayoutChangedError("Technolife detail page has no Product JSON-LD")
        finally:
            await browser_page.close()

    def product_url(self, identifier: str) -> str:
        match = _CODE_RE.fullmatch(identifier.strip())
        if not match:
            raise ValueError(f"Invalid Technolife product identifier: {identifier!r}")
        return f"{self.base_url}/product-{match.group(1)}/"

    @classmethod
    def parse_search_payload(cls, payload: Mapping[str, Any], *, requested_page: int) -> SearchPage:
        try:
            queries = payload["props"]["pageProps"]["dehydratedState"]["queries"]
        except (KeyError, TypeError) as error:
            raise LayoutChangedError(
                "Technolife search data no longer contains dehydratedState.queries"
            ) from error

        search_data: Mapping[str, Any] | None = None
        for query in queries:
            state_data = query.get("state", {}).get("data")
            if not isinstance(state_data, dict):
                continue
            if "results" in state_data and "count" in state_data:
                search_data = state_data
                break
            pages = state_data.get("pages")
            if isinstance(pages, list) and pages and isinstance(pages[0], dict):
                if "results" in pages[0] and "count" in pages[0]:
                    search_data = pages[0]
                    break
        if search_data is None:
            raise LayoutChangedError("Technolife search query contains no results/count contract")

        raw_results = search_data.get("results")
        if not isinstance(raw_results, list):
            raise LayoutChangedError("Technolife search results is not a list")
        products = tuple(cls.parse_search_product(item) for item in raw_results)
        total = parse_int(search_data.get("count")) or 0
        has_next = requested_page * cls.page_size < total
        return SearchPage(
            items=products,
            page=requested_page,
            has_next=has_next,
            total=total,
            next_page=requested_page + 1 if has_next else None,
        )

    @classmethod
    def parse_search_product(cls, data: Mapping[str, Any]) -> Product:
        code = normalize_text(data.get("code"))
        title = normalize_text(data.get("name"))
        match = _CODE_RE.fullmatch(code or "")
        if not match or not title:
            raise LayoutChangedError("Technolife search product is missing code or name")
        identifier = match.group(1)
        current = normalize_price(data.get("discounted_price"), source_currency="IRT")
        original = normalize_price(data.get("normal_price"), source_currency="IRT")
        discount = parse_number(data.get("discount"))
        available = parse_int(data.get("available"))
        review_count = parse_int(data.get("score_count"))
        return Product(
            shop=cls.shop_name,
            identifier=identifier,
            title=title,
            url=f"{cls.base_url}/product-{identifier}/",
            image_url=absolute_url(cls.base_url, data.get("image")),
            current_price=current,
            original_price=original,
            discount_percentage=discount,
            currency="IRT",
            availability=(
                Availability.IN_STOCK
                if available is not None and available > 0
                else Availability.OUT_OF_STOCK
            ),
            rating=normalize_rating(data.get("score_avg")) if review_count else None,
            review_count=review_count,
            popularity=normalize_text(data.get("marketing_group")),
            metadata={
                "object_id": data.get("_id"),
                "query_id": data.get("query_id"),
                "position": data.get("product_position"),
            },
        )

    @classmethod
    def parse_product_payload(cls, data: Mapping[str, Any], *, fallback_url: str) -> Product:
        title = normalize_text(data.get("name"))
        identifier = normalize_text(data.get("sku"))
        if not title or not identifier:
            raise LayoutChangedError("Technolife Product JSON-LD is missing name or sku")
        offers = data.get("offers")
        offers = offers if isinstance(offers, dict) else {}
        nested = offers.get("offers")
        nested_offers = (
            [item for item in nested if isinstance(item, dict)] if isinstance(nested, list) else []
        )
        selected = nested_offers[0] if nested_offers else offers
        # Technolife labels JSON-LD as IRR but displays the same values as toman.
        current_raw = selected.get("price") or offers.get("lowPrice")
        current = normalize_price(current_raw, source_currency="IRT")
        availability = str(selected.get("availability", "")).lower()
        aggregate = data.get("aggregateRating")
        aggregate = aggregate if isinstance(aggregate, dict) else {}
        seller = selected.get("seller")
        seller = seller if isinstance(seller, dict) else {}
        brand = data.get("brand")
        brand = brand if isinstance(brand, dict) else {}
        brand_name = normalize_text(brand.get("name"))
        images = data.get("image")
        image: str | None
        if isinstance(images, list):
            image = str(images[0]) if images else None
        else:
            image = str(images) if images is not None else None
        product_url = absolute_url(cls.base_url, selected.get("url")) or fallback_url
        return Product(
            shop=cls.shop_name,
            identifier=identifier,
            title=title,
            url=product_url,
            image_url=absolute_url(cls.base_url, image),
            current_price=current,
            currency="IRT",
            availability=(
                Availability.IN_STOCK
                if "instock" in availability
                else Availability.OUT_OF_STOCK
                if "outofstock" in availability
                else Availability.UNKNOWN
            ),
            seller=normalize_text(seller.get("name")),
            brand=brand_name.split("|", 1)[0] if brand_name else None,
            rating=normalize_rating(aggregate.get("ratingValue")),
            review_count=parse_int(aggregate.get("reviewCount") or aggregate.get("ratingCount")),
            metadata={"offer_count": parse_int(offers.get("offerCount"))},
        )
