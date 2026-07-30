"""Hamrah Mechanic vehicle-listing adapter."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlencode

from web_scraping.adapters.base import BaseShopAdapter
from web_scraping.exceptions import LayoutChangedError, UnsupportedFeatureError
from web_scraping.models import Availability, Product, SearchPage, SortOption
from web_scraping.normalization import absolute_url, normalize_price, normalize_text, parse_int

_ID_RE = re.compile(r"/(\d+)/?$")


class HamrahMechanicAdapter(BaseShopAdapter):
    """Parse Hamrah Mechanic's stable Next.js page data."""

    shop_name = "hamrahmechanic"
    base_url = "https://www.hamrah-mechanic.com"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._product_urls: dict[str, str] = {}

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
        if sort != SortOption.RELEVANCE:
            raise UnsupportedFeatureError(
                f"Hamrah Mechanic does not expose a verified {sort.value!r} listing sort"
            )
        params: list[tuple[str, object]] = [("page", page)]
        for key, value in (filters or {}).items():
            if isinstance(value, Sequence) and not isinstance(value, str):
                params.extend((key, item) for item in value)
            else:
                params.append((key, value))
        url = f"{self.base_url}/cars-for-sale/?{urlencode(params, doseq=True)}"
        data = await self._next_page_props(url)
        cars_value = data.get("cars")
        cars = cars_value if isinstance(cars_value, Mapping) else {}
        listings = cars.get("list")
        if not isinstance(listings, list):
            raise LayoutChangedError("Hamrah Mechanic page data has no cars.list")
        products = [self.parse_listing(item) for item in listings]
        self._product_urls.update({item.identifier: item.url for item in products})
        needle = normalize_text(keyword)
        if needle:
            products = [item for item in products if needle in item.title]
        total = parse_int(cars.get("totalCount"))
        count = parse_int(cars.get("count")) or len(listings)
        has_next = total is not None and page * count < total
        return SearchPage(
            tuple(products),
            page=page,
            has_next=has_next,
            # The site has no general free-text listing search. With a keyword, matching
            # is performed per page, so the unfiltered catalog total would be misleading.
            total=None if needle else total,
            next_page=page + 1 if has_next else None,
        )

    async def get_product(self, identifier_or_url: str) -> Product:
        if identifier_or_url.startswith(("http://", "https://")):
            url = identifier_or_url
        else:
            try:
                url = self._product_urls[identifier_or_url]
            except KeyError as error:
                raise ValueError(
                    "Hamrah Mechanic bare IDs require a preceding search on the same "
                    "adapter instance; otherwise pass the full product URL"
                ) from error
        data = await self._next_page_props(url)
        details = data.get("orderDetails")
        if not isinstance(details, Mapping):
            raise LayoutChangedError("Hamrah Mechanic detail data has no orderDetails")
        return self.parse_detail(data, fallback_url=url)

    async def _next_page_props(self, url: str) -> Mapping[str, Any]:
        page = await self.session.new_page()
        try:
            await self.session.navigate(page, url)
            text = await page.locator("script#__NEXT_DATA__").text_content()
            if not text:
                raise LayoutChangedError("Hamrah Mechanic page has no __NEXT_DATA__")
            payload = json.loads(text)
            props = payload.get("props", {}).get("pageProps")
            if not isinstance(props, Mapping):
                raise LayoutChangedError("Hamrah Mechanic __NEXT_DATA__ has no pageProps")
            return props
        finally:
            await page.close()

    @classmethod
    def parse_listing(cls, data: Mapping[str, Any]) -> Product:
        identifier = data.get("orderId")
        title = normalize_text(data.get("carNamePersian"))
        path = normalize_text(data.get("exhibitionDetailUrl"))
        if identifier is None or not title or not path:
            raise LayoutChangedError("Hamrah Mechanic listing is missing ID, title, or URL")
        original = normalize_price(data.get("offerPrice"), source_currency="IRT")
        current = normalize_price(data.get("price"), source_currency="IRT")
        return Product(
            shop=cls.shop_name,
            identifier=str(identifier),
            title=title,
            url=absolute_url(cls.base_url, path) or path,
            image_url=absolute_url(cls.base_url, data.get("imageUrl")),
            current_price=current,
            original_price=original if original and current and original > current else None,
            discount_percentage=data.get("offerPriceDifferencePercentage"),
            currency="IRT",
            availability=(
                Availability.OUT_OF_STOCK
                if data.get("isSold")
                else Availability.PREORDER
                if data.get("comingSoon")
                else Availability.IN_STOCK
            ),
            brand=normalize_text(data.get("brandEnglishName")),
            metadata={
                "year": parse_int(data.get("carYear")),
                "mileage_km": parse_int(data.get("km")),
                "city": normalize_text(data.get("cityNamePersian")),
                "neighborhood": normalize_text(data.get("neighborhood")),
                "transmission": normalize_text(data.get("gearBoxPersian")),
                "vehicle_type": normalize_text(data.get("carTypeName")),
                "leasing": bool(data.get("leasingOption")),
            },
        )

    @classmethod
    def parse_detail(cls, data: Mapping[str, Any], *, fallback_url: str) -> Product:
        details_value = data.get("orderDetails")
        details = details_value if isinstance(details_value, Mapping) else data
        car_value = details.get("carInformation")
        car = car_value if isinstance(car_value, Mapping) else {}
        info_value = details.get("orderInformation")
        info = info_value if isinstance(info_value, Mapping) else {}
        breadcrumb = data.get("breadcrumbList")
        identifier = None
        canonical_path = None
        if isinstance(breadcrumb, list) and breadcrumb:
            last = breadcrumb[-1]
            if isinstance(last, Mapping):
                canonical_path = normalize_text(last.get("link"))
                match = _ID_RE.search(canonical_path or "")
                identifier = match.group(1) if match else None
        title_parts = [
            normalize_text(car.get("carBrandName")),
            normalize_text(car.get("carModelName") or car.get("nickName")),
            normalize_text(car.get("carTypeName")),
            str(car.get("carYear")) if car.get("carYear") is not None else None,
        ]
        title = normalize_text(" ".join(part for part in title_parts if part))
        if not identifier or not title:
            raise LayoutChangedError("Hamrah Mechanic detail is missing ID or car information")
        gallery = data.get("gallery")
        first_image = gallery[0] if isinstance(gallery, list) and gallery else {}
        original = normalize_price(car.get("offerPrice"), source_currency="IRT")
        current = normalize_price(car.get("price"), source_currency="IRT")
        return Product(
            shop=cls.shop_name,
            identifier=identifier,
            title=title,
            url=absolute_url(cls.base_url, canonical_path) or fallback_url,
            image_url=absolute_url(
                cls.base_url,
                first_image.get("largeImage") if isinstance(first_image, Mapping) else None,
            ),
            current_price=current,
            original_price=original if original and current and original > current else None,
            discount_percentage=car.get("offerPriceDifferencePercentage"),
            currency="IRT",
            availability=(
                Availability.PREORDER
                if car.get("comingSoon")
                else Availability.IN_STOCK
                if parse_int(car.get("status")) == 1
                else Availability.UNKNOWN
            ),
            seller="همراه مکانیک",
            brand=normalize_text(car.get("carBrandName")),
            metadata={
                "year": parse_int(car.get("carYear")),
                "mileage_km": parse_int(info.get("km")),
                "location": normalize_text(info.get("visitingPlace")),
                "transmission": normalize_text(info.get("gearBox") or car.get("gearBox")),
                "color": normalize_text(info.get("color")),
                "body_condition": normalize_text(info.get("bodyCondition")),
            },
        )
