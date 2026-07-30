"""Public normalized models."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Availability(StrEnum):
    IN_STOCK = "in_stock"
    OUT_OF_STOCK = "out_of_stock"
    PREORDER = "preorder"
    UNKNOWN = "unknown"


class SortOption(StrEnum):
    RELEVANCE = "relevance"
    NEWEST = "newest"
    CHEAPEST = "cheapest"
    MOST_EXPENSIVE = "most_expensive"
    MOST_POPULAR = "most_popular"
    BEST_SELLING = "best_selling"


class CarPriceType(StrEnum):
    MARKET = "market"
    FACTORY = "factory"
    AGENCY = "agency"


class TransportMode(StrEnum):
    FLIGHT = "flight"
    TRAIN = "train"
    BUS = "bus"


@dataclass(frozen=True, slots=True)
class TicketSearchQuery:
    """A route search using the source's documented city, airport, or station codes."""

    mode: TransportMode
    origin: str
    destination: str
    departure_date: date
    return_date: date | None = None
    adults: int = 1
    children: int = 0
    infants: int = 0
    origin_is_city: bool = True
    destination_is_city: bool = True
    cabin_class: str = "allclasses"
    exclusive_coupe: bool = False
    ticket_type: str = "NORMAL"

    def __post_init__(self) -> None:
        if not self.origin.strip() or not self.destination.strip():
            raise ValueError("origin and destination are required")
        if self.origin == self.destination:
            raise ValueError("origin and destination must be different")
        if self.adults < 1 or self.children < 0 or self.infants < 0:
            raise ValueError("passenger counts must include at least one adult")
        if self.return_date is not None and self.return_date < self.departure_date:
            raise ValueError("return_date cannot be before departure_date")


@dataclass(frozen=True, slots=True)
class TicketOffer:
    source: str
    mode: TransportMode
    identifier: str
    origin: str
    destination: str
    departure_at: datetime | None
    arrival_at: datetime | None
    operator: str | None
    service_number: str | None
    price: Decimal
    currency: str = "IRT"
    original_price: Decimal | None = None
    available: bool = True
    remaining_seats: int | None = None
    duration_minutes: int | None = None
    provider: str | None = None
    booking_url: str | None = None
    vehicle_class: str | None = None
    stops: int | None = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class TicketSearchResult:
    query: TicketSearchQuery
    items: tuple[TicketOffer, ...]
    search_url: str
    total: int
    scraped_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class CarPrice:
    identifier: str
    brand: str
    model: str
    trim: str | None
    year: int | None
    price: Decimal
    price_type: CarPriceType
    currency: str = "IRT"
    price_change_percentage: Decimal | None = None
    price_date: str | None = None
    company: str | None = None
    manufacture_type: str | None = None
    url: str | None = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class CarPricePage:
    items: tuple[CarPrice, ...]
    page: int
    has_next: bool
    next_page: int | None = None
    last_updated: str | None = None


@dataclass(frozen=True, slots=True)
class Product:
    shop: str
    identifier: str
    title: str
    url: str
    image_url: str | None = None
    current_price: Decimal | None = None
    original_price: Decimal | None = None
    discount_percentage: Decimal | None = None
    currency: str = "IRT"
    availability: Availability = Availability.UNKNOWN
    seller: str | None = None
    brand: str | None = None
    rating: float | None = None
    review_count: int | None = None
    popularity: str | None = None
    scraped_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class SearchPage:
    items: tuple[Product, ...]
    page: int
    has_next: bool
    total: int | None = None
    next_page: int | None = None
