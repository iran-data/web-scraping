"""Shared interface for passenger transportation sources."""

from __future__ import annotations

from abc import ABC, abstractmethod

from web_scraping.models import TicketSearchQuery, TicketSearchResult, TransportMode
from web_scraping.sources import BaseSource, SourceCategory


class TransportationSource(BaseSource, ABC):
    """A source that searches normalized passenger ticket offers."""

    category = SourceCategory.TRANSPORTATION

    async def search_tickets(self, query: TicketSearchQuery) -> TicketSearchResult:
        if query.mode == TransportMode.FLIGHT:
            return await self.search_flights(query)
        if query.mode == TransportMode.TRAIN:
            return await self.search_trains(query)
        return await self.search_buses(query)

    @abstractmethod
    async def search_flights(self, query: TicketSearchQuery) -> TicketSearchResult:
        """Search flight offers."""

    @abstractmethod
    async def search_trains(self, query: TicketSearchQuery) -> TicketSearchResult:
        """Search train offers."""

    @abstractmethod
    async def search_buses(self, query: TicketSearchQuery) -> TicketSearchResult:
        """Search bus offers."""
