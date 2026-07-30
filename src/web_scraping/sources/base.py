"""Domain-neutral browser-backed source contract."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from web_scraping.browser import BrowserSession
from web_scraping.config import ScraperConfig


class SourceCategory(StrEnum):
    COMMERCE = "commerce"
    TRANSPORTATION = "transportation"
    OTHER = "other"


class SourceCapability(StrEnum):
    SEARCH = "search"
    DETAIL = "detail"
    PAGINATION = "pagination"
    FILTERS = "filters"
    SORTING = "sorting"
    POPULAR = "popular"
    BEST_SELLING = "best_selling"
    REFERENCE_PRICES = "reference_prices"
    FLIGHT_SEARCH = "flight_search"
    TRAIN_SEARCH = "train_search"
    BUS_SEARCH = "bus_search"


class BaseSource:
    """Browser lifecycle shared by every source domain."""

    category: SourceCategory = SourceCategory.OTHER
    capabilities: frozenset[SourceCapability] = frozenset()

    @property
    def source_name(self) -> str:
        """Stable registry name used independently of a source's domain."""
        raise NotImplementedError

    def __init__(
        self,
        config: ScraperConfig | None = None,
        *,
        session: BrowserSession | None = None,
    ) -> None:
        self.config = config or ScraperConfig()
        self.session = session or BrowserSession(self.config)
        self._owns_session = session is None

    async def __aenter__(self) -> Self:
        await self.session.start()
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owns_session:
            await self.session.close()
