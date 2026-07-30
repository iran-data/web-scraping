"""Domain-neutral source registry and backward-compatible commerce factory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from web_scraping.adapters.bama import BamaAdapter
from web_scraping.adapters.base import CommerceAdapter
from web_scraping.adapters.digikala import DigikalaAdapter
from web_scraping.adapters.digikalajet import DigikalaJetAdapter
from web_scraping.adapters.hamrah_mechanic import HamrahMechanicAdapter
from web_scraping.adapters.safarmarket import SafarmarketAdapter
from web_scraping.adapters.snappmarket import SnappMarketAdapter
from web_scraping.adapters.snappshop import SnappShopAdapter
from web_scraping.adapters.technolife import TechnolifeAdapter
from web_scraping.adapters.torob import TorobAdapter
from web_scraping.sources import BaseSource, SourceCategory

if TYPE_CHECKING:
    from web_scraping.config import ScraperConfig

_SOURCES: dict[str, type[BaseSource]] = {
    "bama": BamaAdapter,
    "digikala": DigikalaAdapter,
    "digikalajet": DigikalaJetAdapter,
    "hamrahmechanic": HamrahMechanicAdapter,
    "safarmarket": SafarmarketAdapter,
    "snappmarket": SnappMarketAdapter,
    "snappshop": SnappShopAdapter,
    "technolife": TechnolifeAdapter,
    "torob": TorobAdapter,
}


def supported_sources(category: SourceCategory | None = None) -> tuple[str, ...]:
    """Return registered sources, optionally restricted to one domain category."""
    return tuple(
        sorted(
            name
            for name, source_type in _SOURCES.items()
            if category is None or source_type.category == category
        )
    )


def create_source(name: str, config: ScraperConfig | None = None) -> BaseSource:
    """Create any registered source without assuming its output domain."""
    try:
        source_type = _SOURCES[name.lower()]
    except KeyError as error:
        raise ValueError(
            f"Unsupported source {name!r}; choose one of: {', '.join(supported_sources())}"
        ) from error
    return source_type(config)


def supported_shops() -> tuple[str, ...]:
    """Compatibility alias returning commerce-category sources."""
    return supported_sources(SourceCategory.COMMERCE)


def create_adapter(shop: str, config: ScraperConfig | None = None) -> CommerceAdapter:
    """Compatibility factory for the shared commerce interface."""
    source = create_source(shop, config)
    if not isinstance(source, CommerceAdapter):
        raise ValueError(
            f"Source {shop!r} is not a commerce adapter; choose one of: "
            f"{', '.join(supported_shops())}"
        )
    return source
