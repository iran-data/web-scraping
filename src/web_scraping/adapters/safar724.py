"""Safar724 intercity bus ticket source."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import quote

from playwright.async_api import APIResponse, Response

from web_scraping.exceptions import LayoutChangedError, NavigationError, UnsupportedFeatureError
from web_scraping.models import (
    TicketOffer,
    TicketSearchQuery,
    TicketSearchResult,
    TransportMode,
)
from web_scraping.normalization import (
    gregorian_to_jalali,
    normalize_price,
    normalize_text,
    parse_int,
    parse_number,
)
from web_scraping.sources import SourceCapability
from web_scraping.transportation import TransportationSource


class Safar724Adapter(TransportationSource):
    """Search public Safar724 bus routes through its rendered first-party flow."""

    base_url = "https://safar724.com"
    capabilities = frozenset({SourceCapability.BUS_SEARCH})

    @property
    def source_name(self) -> str:
        return "safar724"

    async def search_flights(self, query: TicketSearchQuery) -> TicketSearchResult:
        raise UnsupportedFeatureError("Safar724 specializes in bus tickets")

    async def search_trains(self, query: TicketSearchQuery) -> TicketSearchResult:
        raise UnsupportedFeatureError("Safar724 specializes in bus tickets")

    async def search_buses(self, query: TicketSearchQuery) -> TicketSearchResult:
        if query.mode != TransportMode.BUS:
            raise ValueError(f"expected a bus query, got {query.mode.value}")
        cities = await self._get_cities()
        origin = self.resolve_city(cities, query.origin)
        destination = self.resolve_city(cities, query.destination)
        if origin["Code"] == destination["Code"]:
            raise ValueError("origin and destination resolve to the same city")
        url = self.bus_search_url(
            str(origin["Name"]),
            str(destination["Name"]),
            query,
        )
        payload = await self._capture_route(url)
        items_value = payload.get("items")
        if not isinstance(items_value, list):
            raise LayoutChangedError("Safar724 bus response has no items list")
        items = tuple(
            self.parse_bus(item, query=query, route=payload, search_url=url)
            for item in items_value
            if isinstance(item, Mapping)
        )
        return TicketSearchResult(query, items, url, len(items))

    async def _get_cities(self) -> list[Mapping[str, Any]]:
        url = f"{self.base_url}/route/getcities"
        await self.session.start()

        async def operation() -> APIResponse:
            return await self.session.context.request.get(
                url, timeout=self.config.navigation_timeout_ms
            )

        response = await self.session.run(operation, operation_name="safar724_city_lookup", url=url)
        if response.status >= 400:
            raise NavigationError(f"Safar724 city lookup returned HTTP {response.status}")
        payload: object = await response.json()
        if not isinstance(payload, list):
            raise LayoutChangedError("Safar724 city lookup returned non-list JSON")
        cities = [item for item in payload if isinstance(item, Mapping)]
        if not cities:
            raise LayoutChangedError("Safar724 city lookup returned no valid cities")
        return cities

    async def _capture_route(self, url: str) -> Mapping[str, Any]:
        page = await self.session.new_page()
        try:

            async def operation() -> Response:
                async with page.expect_response(
                    lambda response: "/cs/api/bus/route" in response.url,
                    timeout=self.config.navigation_timeout_ms,
                ) as pending:
                    navigation = await page.goto(url, wait_until="domcontentloaded")
                    if navigation is not None and navigation.status >= 500:
                        raise NavigationError(f"{url} returned HTTP {navigation.status}")
                return await pending.value

            response = await self.session.run(
                operation, operation_name="safar724_bus_search", url=url
            )
            if response.status >= 400:
                raise NavigationError(f"Safar724 bus route API returned HTTP {response.status}")
            payload: object = await response.json()
            if not isinstance(payload, Mapping):
                raise LayoutChangedError("Safar724 bus route returned non-object JSON")
            return payload
        finally:
            await page.close()

    @classmethod
    def bus_search_url(
        cls,
        origin_slug: str,
        destination_slug: str,
        query: TicketSearchQuery,
    ) -> str:
        jalali_date = gregorian_to_jalali(query.departure_date)
        return (
            f"{cls.base_url}/bus/{quote(origin_slug.lower())}-"
            f"{quote(destination_slug.lower())}?date={jalali_date}"
        )

    @staticmethod
    def resolve_city(cities: list[Mapping[str, Any]], identifier: str) -> Mapping[str, Any]:
        needle = normalize_text(identifier)
        if not needle:
            raise ValueError("city identifier cannot be empty")
        needle_lower = needle.lower()
        for city in cities:
            candidates = (city.get("Code"), city.get("Name"), city.get("PersianName"))
            normalized_candidates = [
                text
                for candidate in candidates
                if candidate is not None and (text := normalize_text(str(candidate))) is not None
            ]
            if any(text.lower() == needle_lower for text in normalized_candidates):
                if not city.get("Code") or not city.get("Name") or not city.get("PersianName"):
                    raise LayoutChangedError(
                        "Safar724 city is missing code, English name, or Persian name"
                    )
                return city
        raise ValueError(
            f"Unknown Safar724 city {identifier!r}; use a city code, English slug, "
            "or exact Persian name from /route/getcities"
        )

    @classmethod
    def parse_bus(
        cls,
        data: Mapping[str, Any],
        *,
        query: TicketSearchQuery,
        route: Mapping[str, Any],
        search_url: str,
    ) -> TicketOffer:
        identifier = data.get("id")
        price = normalize_price(data.get("price"), source_currency="IRR")
        departure_time = normalize_text(
            str(data.get("departureTime")) if data.get("departureTime") is not None else None
        )
        origin = normalize_text(route.get("originPersianName"))
        destination = normalize_text(route.get("destinationPersianName"))
        if (
            identifier is None
            or price is None
            or not departure_time
            or not origin
            or not destination
        ):
            raise LayoutChangedError(
                "Safar724 ticket is missing ID, route, departure time, or price"
            )
        departure = cls._departure_datetime(query, departure_time)
        remaining = parse_int(data.get("availableSeatCount"))
        discount = parse_number(data.get("discountPercentage"))
        original_price = cls._original_price(price, discount)
        status = normalize_text(str(data.get("status")) if data.get("status") is not None else None)
        facilities = data.get("facilities")
        refund_rules = data.get("refundRules")
        return TicketOffer(
            source="safar724",
            mode=TransportMode.BUS,
            identifier=str(identifier),
            origin=origin,
            destination=destination,
            departure_at=departure,
            arrival_at=None,
            operator=normalize_text(data.get("companyPersianName")),
            service_number=str(identifier),
            price=price,
            original_price=original_price,
            available=status == "Available" and (remaining is None or remaining > 0),
            remaining_seats=remaining,
            provider="Safar724",
            booking_url=search_url,
            vehicle_class=normalize_text(data.get("busType")),
            metadata={
                "vehicle_type": normalize_text(data.get("vehicleType")),
                "is_vip": bool(data.get("isVip", False)),
                "is_special_charter": bool(data.get("isSpecialCharter", False)),
                "capacity": parse_int(data.get("capacity")),
                "origin_terminal": normalize_text(data.get("originTerminalPersianName")),
                "destination_terminal": normalize_text(data.get("destinationTerminalPersianName")),
                "company_code": normalize_text(data.get("companyCode")),
                "facilities": facilities if isinstance(facilities, list) else [],
                "refund_rules": refund_rules if isinstance(refund_rules, list) else [],
                "discount_percentage": discount,
            },
        )

    @staticmethod
    def _departure_datetime(query: TicketSearchQuery, raw_time: str) -> datetime:
        try:
            hour, minute = (int(part) for part in raw_time.split(":")[:2])
            return datetime.combine(
                query.departure_date,
                datetime.min.time(),
            ).replace(hour=hour, minute=minute)
        except (TypeError, ValueError) as error:
            raise LayoutChangedError(
                f"Safar724 returned invalid departure time {raw_time!r}"
            ) from error

    @staticmethod
    def _original_price(price: Decimal, discount: Decimal | None) -> Decimal | None:
        if discount is None or discount <= 0 or discount >= 100:
            return None
        return price / (Decimal(1) - discount / Decimal(100))
