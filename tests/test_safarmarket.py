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
from web_scraping.adapters.safarmarket import SafarmarketAdapter
from web_scraping.exceptions import LayoutChangedError

FIXTURES = Path(__file__).parent / "fixtures" / "safarmarket"


def query(mode: TransportMode) -> TicketSearchQuery:
    return TicketSearchQuery(
        mode=mode,
        origin="THR" if mode == TransportMode.FLIGHT else "1",
        destination="MHD" if mode == TransportMode.FLIGHT else "2",
        departure_date=date(2026, 8, 5),
    )


def test_transportation_registry_and_capabilities() -> None:
    source = create_source("safarmarket")
    assert isinstance(source, TransportationSource)
    assert source.category == SourceCategory.TRANSPORTATION
    assert supported_sources(SourceCategory.TRANSPORTATION) == ("safarmarket",)
    assert source.capabilities == {
        SourceCapability.FLIGHT_SEARCH,
        SourceCapability.TRAIN_SEARCH,
        SourceCapability.BUS_SEARCH,
    }


def test_query_validation() -> None:
    with pytest.raises(ValueError, match="different"):
        TicketSearchQuery(TransportMode.FLIGHT, "THR", "THR", date(2026, 8, 5))
    with pytest.raises(ValueError, match="adult"):
        TicketSearchQuery(TransportMode.TRAIN, "1", "2", date(2026, 8, 5), adults=0)
    with pytest.raises(ValueError, match="return_date"):
        TicketSearchQuery(
            TransportMode.FLIGHT,
            "THR",
            "MHD",
            date(2026, 8, 5),
            return_date=date(2026, 8, 4),
        )


def test_search_url_contracts() -> None:
    assert SafarmarketAdapter.flight_search_url(query(TransportMode.FLIGHT)) == (
        "https://safarmarket.com/flights/cTHR-cMHD/2026-08-05/0/"
        "allclasses/1adults/0children/0infants"
    )
    assert SafarmarketAdapter.train_search_url(query(TransportMode.TRAIN)) == (
        "https://safarmarket.com/trains/1-2/2026-08-05/0/"
        "1adults/0children/0infants/non_coupe/NORMAL"
    )
    assert "departure-date=1405-05-14" in SafarmarketAdapter.bus_search_url(
        query(TransportMode.BUS)
    )


def test_parse_flight_normalizes_rial_to_toman() -> None:
    payload = json.loads((FIXTURES / "flights.json").read_text())
    offer = SafarmarketAdapter.parse_flight(payload["result"]["flights"][0])
    assert offer.mode == TransportMode.FLIGHT
    assert offer.identifier == "1234:2026-08-05T04:00:00"
    assert offer.origin == "تهران"
    assert offer.destination == "مشهد"
    assert offer.price == Decimal("7400822.2")
    assert offer.currency == "IRT"
    assert offer.remaining_seats == 4
    assert offer.provider == "آژانس نمونه"
    assert offer.duration_minutes == 90
    assert offer.stops == 0


def test_parse_train_handles_overnight_arrival_and_prices() -> None:
    payload = json.loads((FIXTURES / "trains.json").read_text())
    offer = SafarmarketAdapter.parse_train(
        payload["payload"]["result"]["depArr"][0],
        query=query(TransportMode.TRAIN),
    )
    assert offer.price == Decimal("1520000")
    assert offer.original_price == Decimal("1600000")
    assert offer.departure_at is not None
    assert offer.arrival_at is not None
    assert offer.arrival_at.date() == date(2026, 8, 6)
    assert offer.available
    assert offer.remaining_seats == 3
    assert offer.operator == "رجا"
    assert offer.stops == 1


def test_parsers_report_layout_changes() -> None:
    with pytest.raises(LayoutChangedError, match="leave"):
        SafarmarketAdapter.parse_flight({})
    with pytest.raises(LayoutChangedError, match="ID"):
        SafarmarketAdapter.parse_train({}, query=query(TransportMode.TRAIN))


@pytest.mark.asyncio
async def test_search_dispatches_by_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    source = SafarmarketAdapter()
    called: list[TransportMode] = []

    async def fake_search(value: TicketSearchQuery) -> object:
        called.append(value.mode)
        return object()

    monkeypatch.setattr(source, "search_flights", fake_search)
    await source.search_tickets(query(TransportMode.FLIGHT))
    assert called == [TransportMode.FLIGHT]
