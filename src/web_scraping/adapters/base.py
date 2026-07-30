"""Commerce-specific adapter contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence

from web_scraping.models import Product, SearchPage, SortOption
from web_scraping.sources import BaseSource, SourceCapability, SourceCategory


class CommerceAdapter(BaseSource, ABC):
    """Common product interface implemented by commerce sources."""

    shop_name: str
    base_url: str
    category = SourceCategory.COMMERCE
    capabilities = frozenset(
        {
            SourceCapability.SEARCH,
            SourceCapability.DETAIL,
            SourceCapability.PAGINATION,
            SourceCapability.FILTERS,
        }
    )

    @property
    def source_name(self) -> str:
        """Domain-neutral name while preserving the Product.shop field."""
        return self.shop_name

    @abstractmethod
    async def search(
        self,
        keyword: str,
        *,
        page: int = 1,
        sort: SortOption = SortOption.RELEVANCE,
        filters: Mapping[str, str | int | bool | Sequence[str]] | None = None,
    ) -> SearchPage:
        """Return one normalized search-result page."""

    @abstractmethod
    async def get_product(self, identifier_or_url: str) -> Product:
        """Fetch and normalize a product detail page."""

    async def iter_search(
        self,
        keyword: str,
        *,
        start_page: int = 1,
        max_pages: int | None = None,
        sort: SortOption = SortOption.RELEVANCE,
        filters: Mapping[str, str | int | bool | Sequence[str]] | None = None,
    ) -> AsyncIterator[Product]:
        page_number = start_page
        pages_seen = 0
        while max_pages is None or pages_seen < max_pages:
            result = await self.search(keyword, page=page_number, sort=sort, filters=filters)
            for product in result.items:
                yield product
            pages_seen += 1
            if not result.has_next or result.next_page is None:
                break
            page_number = result.next_page

    async def popular(self, *, limit: int = 20) -> tuple[Product, ...]:
        result = await self.search("", sort=SortOption.MOST_POPULAR)
        return result.items[:limit]

    async def best_selling(self, *, limit: int = 20) -> tuple[Product, ...]:
        result = await self.search("", sort=SortOption.BEST_SELLING)
        return result.items[:limit]


# Compatibility name retained for applications built before the generic source layer.
BaseShopAdapter = CommerceAdapter
