"""Async, normalized scrapers for heterogeneous Iranian web sources."""

from web_scraping.adapters import CommerceAdapter
from web_scraping.config import ScraperConfig
from web_scraping.models import (
    Availability,
    CarPrice,
    CarPricePage,
    CarPriceType,
    Product,
    SearchPage,
    SortOption,
    TicketOffer,
    TicketSearchQuery,
    TicketSearchResult,
    TransportMode,
)
from web_scraping.registry import (
    create_adapter,
    create_source,
    supported_shops,
    supported_sources,
)
from web_scraping.sources import BaseSource, SourceCapability, SourceCategory
from web_scraping.transportation import TransportationSource

__all__ = [
    "Availability",
    "BaseSource",
    "CarPrice",
    "CarPricePage",
    "CarPriceType",
    "CommerceAdapter",
    "Product",
    "ScraperConfig",
    "SearchPage",
    "SortOption",
    "SourceCapability",
    "SourceCategory",
    "TicketOffer",
    "TicketSearchQuery",
    "TicketSearchResult",
    "TransportMode",
    "TransportationSource",
    "create_adapter",
    "create_source",
    "supported_shops",
    "supported_sources",
]
