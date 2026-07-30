"""Safarmarket flight and train ticket source."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from playwright.async_api import Response

from web_scraping.exceptions import (
    LayoutChangedError,
    NavigationError,
    UnsupportedFeatureError,
)
from web_scraping.models import (
    TicketOffer,
    TicketSearchQuery,
    TicketSearchResult,
    TransportMode,
)
from web_scraping.normalization import absolute_url, normalize_price, normalize_text, parse_int
from web_scraping.sources import SourceCapability
from web_scraping.transportation import TransportationSource


class SafarmarketAdapter(TransportationSource):
    """Search Safarmarket by following its public browser result flows."""

    base_url = "https://safarmarket.com"
    capabilities = frozenset(
        {
            SourceCapability.FLIGHT_SEARCH,
            SourceCapability.TRAIN_SEARCH,
        }
    )

    @property
    def source_name(self) -> str:
        return "safarmarket"

    async def search_flights(self, query: TicketSearchQuery) -> TicketSearchResult:
        self._require_mode(query, TransportMode.FLIGHT)
        url = self.flight_search_url(query)
        payload = await self._capture_json(url, "/api/flight/v3/search")
        result = payload.get("result")
        flights = result.get("flights") if isinstance(result, Mapping) else None
        if not isinstance(flights, list):
            raise LayoutChangedError("Safarmarket flight response has no result.flights list")
        items = tuple(self.parse_flight(item) for item in flights if isinstance(item, Mapping))
        return TicketSearchResult(query, items, url, len(items))

    async def search_trains(self, query: TicketSearchQuery) -> TicketSearchResult:
        self._require_mode(query, TransportMode.TRAIN)
        url = self.train_search_url(query)
        payload = await self._capture_json(url, "/api/train/v2/search")
        outer = payload.get("payload")
        result = outer.get("result") if isinstance(outer, Mapping) else None
        trains = result.get("depArr") if isinstance(result, Mapping) else None
        if not isinstance(trains, list):
            raise LayoutChangedError("Safarmarket train response has no payload.result.depArr list")
        items = tuple(
            self.parse_train(item, query=query) for item in trains if isinstance(item, Mapping)
        )
        return TicketSearchResult(query, items, url, len(items))

    async def search_buses(self, query: TicketSearchQuery) -> TicketSearchResult:
        raise UnsupportedFeatureError(
            "Safarmarket bus search is not supported; use the Safar724 transportation source"
        )

    async def _capture_json(self, url: str, endpoint: str) -> Mapping[str, Any]:
        page = await self.session.new_page()
        try:

            async def operation() -> Response:
                async with page.expect_response(
                    lambda response: endpoint in response.url,
                    timeout=self.config.navigation_timeout_ms,
                ) as pending:
                    navigation = await page.goto(url, wait_until="domcontentloaded")
                    if navigation is not None and navigation.status >= 500:
                        raise NavigationError(f"{url} returned HTTP {navigation.status}")
                return await pending.value

            response = await self.session.run(
                operation, operation_name="safarmarket_search", url=url
            )
            if response.status >= 400:
                raise NavigationError(f"{endpoint} returned HTTP {response.status}")
            payload: object = await response.json()
            if not isinstance(payload, Mapping):
                raise LayoutChangedError(f"Safarmarket {endpoint} returned non-object JSON")
            return payload
        finally:
            await page.close()

    @classmethod
    def flight_search_url(cls, query: TicketSearchQuery) -> str:
        origin = ("c" if query.origin_is_city else "a") + query.origin
        destination = ("c" if query.destination_is_city else "a") + query.destination
        return_date = query.return_date.isoformat() if query.return_date else "0"
        return (
            f"{cls.base_url}/flights/{origin}-{destination}/"
            f"{query.departure_date.isoformat()}/{return_date}/{query.cabin_class}/"
            f"{query.adults}adults/{query.children}children/{query.infants}infants"
        )

    @classmethod
    def train_search_url(cls, query: TicketSearchQuery) -> str:
        return_date = query.return_date.isoformat() if query.return_date else "0"
        coupe = "coupe" if query.exclusive_coupe else "non_coupe"
        return (
            f"{cls.base_url}/trains/{query.origin}-{query.destination}/"
            f"{query.departure_date.isoformat()}/{return_date}/{query.adults}adults/"
            f"{query.children}children/{query.infants}infants/{coupe}/{query.ticket_type}"
        )

    @classmethod
    def parse_flight(cls, data: Mapping[str, Any]) -> TicketOffer:
        leave = data.get("leave")
        if not isinstance(leave, Mapping):
            raise LayoutChangedError("Safarmarket flight is missing leave details")
        providers_value = data.get("providers")
        providers = (
            [item for item in providers_value if isinstance(item, Mapping)]
            if isinstance(providers_value, list)
            else []
        )
        priced = [
            item for item in providers if normalize_price(item.get("price"), source_currency="IRR")
        ]
        provider = min(
            priced,
            key=lambda item: (
                normalize_price(item.get("price"), source_currency="IRR") or Decimal("Infinity")
            ),
            default=None,
        )
        price = normalize_price(
            provider.get("price") if provider else data.get("minPrice"),
            source_currency="IRR",
        )
        departure = _parse_datetime(leave.get("departureTime"))
        flight_number = normalize_text(leave.get("flightNo"))
        if price is None or departure is None or not flight_number:
            raise LayoutChangedError(
                "Safarmarket flight is missing flight number, departure time, or price"
            )
        legs_value = leave.get("legs")
        legs = (
            [item for item in legs_value if isinstance(item, Mapping)]
            if isinstance(legs_value, list)
            else []
        )
        first_leg = legs[0] if legs else {}
        last_leg = legs[-1] if legs else {}
        origin = _place_name(first_leg, "origin") or normalize_text(leave.get("sourceAirportCode"))
        destination = _place_name(last_leg, "destination") or normalize_text(
            leave.get("targetAirportCode")
        )
        if not origin or not destination:
            raise LayoutChangedError("Safarmarket flight is missing route details")
        remaining = parse_int(provider.get("capacity") if provider else leave.get("capacity"))
        return TicketOffer(
            source="safarmarket",
            mode=TransportMode.FLIGHT,
            identifier=f"{flight_number}:{departure.isoformat()}",
            origin=origin,
            destination=destination,
            departure_at=departure,
            arrival_at=_parse_datetime(leave.get("arrivalTime")),
            operator=normalize_text(leave.get("airlineNameFa")),
            service_number=flight_number,
            price=price,
            available=bool(data.get("reservable", True)) and (remaining is None or remaining > 0),
            remaining_seats=remaining,
            duration_minutes=parse_int(leave.get("duration")),
            provider=normalize_text(provider.get("title") if provider else None),
            booking_url=absolute_url(
                cls.base_url, str(provider.get("url")) if provider and provider.get("url") else None
            ),
            vehicle_class=normalize_text(data.get("flightClass")),
            stops=parse_int(leave.get("stopsCount")),
            metadata={
                "airline_code": normalize_text(leave.get("airlineCode")),
                "sell_type": normalize_text(leave.get("sellType")),
                "charter": bool(leave.get("charter", False)),
                "provider_count": parse_int(data.get("providersCount")),
            },
        )

    @classmethod
    def parse_train(cls, data: Mapping[str, Any], *, query: TicketSearchQuery) -> TicketOffer:
        identifier = normalize_text(data.get("sTid"))
        number_value = data.get("trainNumber")
        number = normalize_text(str(number_value)) if number_value is not None else None
        price = normalize_price(data.get("cost"), source_currency="IRR")
        departure = _train_departure(data)
        if not identifier or price is None or departure is None:
            raise LayoutChangedError("Safarmarket train is missing ID, departure time, or price")
        arrival = _time_on_or_after(departure, data.get("timeOfArrival"))
        remaining = parse_int(data.get("counting"))
        return TicketOffer(
            source="safarmarket",
            mode=TransportMode.TRAIN,
            identifier=identifier,
            origin=query.origin,
            destination=query.destination,
            departure_at=departure,
            arrival_at=arrival,
            operator=normalize_text(data.get("ownerSecondaryName")),
            service_number=number,
            price=price,
            original_price=normalize_price(data.get("fullPrice"), source_currency="IRR"),
            available=remaining is None or remaining > 0,
            remaining_seats=remaining,
            duration_minutes=parse_int(data.get("duration")),
            vehicle_class=normalize_text(data.get("wagonName")),
            stops=_sequence_length(data.get("stops")),
            metadata={
                "coupe_seat_type": normalize_text(data.get("coupeSeatType")),
                "compartment_capacity": parse_int(data.get("compartmentCapacity")),
                "is_compartment": bool(data.get("isCompartment", False)),
                "exclusive_coupe": bool(data.get("canExclusive", False)),
            },
        )

    @staticmethod
    def _require_mode(query: TicketSearchQuery, expected: TransportMode) -> None:
        if query.mode != expected:
            raise ValueError(f"expected a {expected.value} query, got {query.mode.value}")


def _place_name(leg: Mapping[str, Any], side: str) -> str | None:
    value = leg.get(side)
    if isinstance(value, Mapping):
        return normalize_text(value.get("cityNameFa") or value.get("nameFa") or value.get("code"))
    if value is not None:
        return normalize_text(str(value))
    prefix = "departure" if side == "origin" else "arrival"
    candidate = (
        leg.get(f"{prefix}CityNamePersian")
        or leg.get(f"{prefix}CityName")
        or leg.get(f"{prefix}AirportCode")
    )
    return normalize_text(str(candidate)) if candidate is not None else None


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _train_departure(data: Mapping[str, Any]) -> datetime | None:
    raw_date = normalize_text(data.get("depStationDate"))
    raw_time = normalize_text(data.get("exitTime"))
    if not raw_date or not raw_time:
        return None
    return _parse_datetime(f"{raw_date} {raw_time}")


def _time_on_or_after(departure: datetime, value: object) -> datetime | None:
    raw = normalize_text(str(value)) if value is not None else None
    if not raw:
        return None
    try:
        hour, minute = (int(part) for part in raw.split(":")[:2])
    except (TypeError, ValueError):
        return None
    arrival = departure.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return arrival if arrival >= departure else arrival + timedelta(days=1)


def _sequence_length(value: object) -> int | None:
    return len(value) if isinstance(value, Sequence) and not isinstance(value, str) else None
