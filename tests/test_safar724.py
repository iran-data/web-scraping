from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from web_scraping import (
    SourceCapability,
    SourceCategory,
    TicketSearchQuery,
    TransportationSource,
    TransportMode,
    create_source,
    supported_sources,
)
from web_scraping.adapters.safar724 import Safar724Adapter
from web_scraping.exceptions import LayoutChangedError, UnsupportedFeatureError

FIXTURES = Path(__file__).parent / "fixtures" / "safar724"


def bus_query(origin: str = "11320000", destination: str = "31310000") -> TicketSearchQuery:
    return TicketSearchQuery(
        mode=TransportMode.BUS,
        origin=origin,
        destination=destination,
        departure_date=date(2026, 8, 14),
    )


def load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text())


def test_registry_and_bus_only_capability() -> None:
    source = create_source("safar724")
    assert isinstance(source, TransportationSource)
    assert source.category == SourceCategory.TRANSPORTATION
    assert source.capabilities == {SourceCapability.BUS_SEARCH}
    assert supported_sources(SourceCategory.TRANSPORTATION) == ("safar724", "safarmarket")


def test_city_resolution_accepts_code_slug_and_persian_name() -> None:
    cities = load("cities.json")
    assert isinstance(cities, list)
    assert Safar724Adapter.resolve_city(cities, "11320000")["Name"] == "tehran"
    assert Safar724Adapter.resolve_city(cities, "MASHHAD")["Code"] == "31310000"
    assert Safar724Adapter.resolve_city(cities, " تهران ")["Code"] == "11320000"
    with pytest.raises(ValueError, match="Unknown"):
        Safar724Adapter.resolve_city(cities, "not-a-city")


def test_bus_url_uses_verified_route_and_jalali_date() -> None:
    assert Safar724Adapter.bus_search_url("tehran", "mashhad", bus_query()) == (
        "https://safar724.com/bus/tehran-mashhad?date=1405-05-23"
    )


def test_parse_bus_normalizes_rial_and_details() -> None:
    route = load("route.json")
    assert isinstance(route, dict)
    offer = Safar724Adapter.parse_bus(
        route["items"][0],
        query=bus_query(),
        route=route,
        search_url="https://safar724.com/bus/tehran-mashhad?date=1405-05-23",
    )
    assert offer.source == "safar724"
    assert offer.mode == TransportMode.BUS
    assert offer.identifier == "39187726"
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.departure_at is not None
    assert offer.departure_at.isoformat() == "2026-08-14T06:00:00"
    assert offer.price == Decimal("1315500")
    assert offer.currency == "IRT"
    assert offer.operator == "تعاونی 12 گیتی نورد"
    assert offer.remaining_seats == 23
    assert offer.available
    assert offer.metadata["is_vip"] is True
    assert offer.metadata["origin_terminal"] == "جنوب (خزانه)"
    assert offer.metadata["facilities"] == ["شارژر"]


def test_parse_bus_detects_bad_contract_and_time() -> None:
    with pytest.raises(LayoutChangedError, match="missing"):
        Safar724Adapter.parse_bus(
            {},
            query=bus_query(),
            route={},
            search_url="https://safar724.com/",
        )
    route = load("route.json")
    assert isinstance(route, dict)
    item = dict(route["items"][0])
    item["departureTime"] = "invalid"
    with pytest.raises(LayoutChangedError, match="departure time"):
        Safar724Adapter.parse_bus(
            item,
            query=bus_query(),
            route=route,
            search_url="https://safar724.com/",
        )


@pytest.mark.asyncio
async def test_bus_search_resolves_cities_and_parses_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = Safar724Adapter()
    cities = load("cities.json")
    route = load("route.json")
    assert isinstance(cities, list)
    assert isinstance(route, dict)

    async def fake_cities() -> list[dict[str, object]]:
        return cities

    async def fake_route(url: str) -> dict[str, object]:
        assert url.endswith("/bus/tehran-mashhad?date=1405-05-23")
        return route

    monkeypatch.setattr(source, "_get_cities", fake_cities)
    monkeypatch.setattr(source, "_capture_route", fake_route)
    result = await source.search_buses(bus_query())
    assert result.total == 1
    assert result.items[0].price == Decimal("1315500")


@pytest.mark.asyncio
async def test_non_bus_modes_are_explicitly_unsupported() -> None:
    source = Safar724Adapter()
    flight = TicketSearchQuery(
        TransportMode.FLIGHT,
        "THR",
        "MHD",
        date(2026, 8, 14),
    )
    with pytest.raises(UnsupportedFeatureError, match="bus"):
        await source.search_flights(flight)
    with pytest.raises(UnsupportedFeatureError, match="bus"):
        await source.search_trains(flight)
