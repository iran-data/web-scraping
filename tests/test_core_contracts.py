from __future__ import annotations

from argparse import Namespace
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

import pytest

from web_scraping import Product, SearchPage, SortOption
from web_scraping.adapters.base import CommerceAdapter
from web_scraping.cli import build_parser, run
from web_scraping.registry import create_adapter, create_source
from web_scraping.serialization import jsonable


class DummyAdapter(CommerceAdapter):
    shop_name = "dummy"
    base_url = "https://example.test"

    def __init__(self) -> None:
        super().__init__()
        self.sorts: list[SortOption] = []

    async def __aenter__(self) -> DummyAdapter:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def search(
        self,
        keyword: str,
        *,
        page: int = 1,
        sort: SortOption = SortOption.RELEVANCE,
        filters: Mapping[str, str | int | bool | Sequence[str]] | None = None,
    ) -> SearchPage:
        del keyword, filters
        self.sorts.append(sort)
        item = Product(
            shop=self.shop_name,
            identifier=str(page),
            title=f"item {page}",
            url=f"{self.base_url}/{page}",
        )
        return SearchPage(
            (item,),
            page=page,
            has_next=page < 2,
            next_page=page + 1 if page < 2 else None,
        )

    async def get_product(self, identifier_or_url: str) -> Product:
        return Product(
            shop=self.shop_name,
            identifier=identifier_or_url,
            title="detail",
            url=f"{self.base_url}/{identifier_or_url}",
        )


@pytest.mark.asyncio
async def test_commerce_iteration_and_convenience_sorts() -> None:
    adapter = DummyAdapter()
    items = [item async for item in adapter.iter_search("query")]
    assert [item.identifier for item in items] == ["1", "2"]

    popular = await adapter.popular(limit=1)
    best = await adapter.best_selling(limit=1)
    assert len(popular) == len(best) == 1
    assert adapter.sorts[-2:] == [
        SortOption.MOST_POPULAR,
        SortOption.BEST_SELLING,
    ]


def test_registry_errors_are_domain_specific() -> None:
    with pytest.raises(ValueError, match="Unsupported source"):
        create_source("missing")
    with pytest.raises(ValueError, match="Unsupported source"):
        create_adapter("missing")


def test_cli_parser_exposes_commerce_and_bama_price_commands() -> None:
    search = build_parser().parse_args(["search", "digikala", "گوشی", "--page", "2"])
    assert search.command == "search"
    assert search.page == 2

    prices = build_parser().parse_args(["bama-prices", "پژو", "--type", "factory"])
    assert prices.command == "bama-prices"
    assert prices.keyword == "پژو"
    assert prices.type == "factory"

    tickets = build_parser().parse_args(["tickets", "bus", "tehran", "mashhad", "2026-08-14"])
    assert tickets.command == "tickets"
    assert tickets.mode == "bus"
    assert tickets.origin == "tehran"
    assert tickets.destination == "mashhad"


@pytest.mark.asyncio
async def test_cli_run_dispatches_search_and_product(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = DummyAdapter()
    monkeypatch.setattr("web_scraping.cli.create_adapter", lambda *_: adapter)
    common = {
        "visible": False,
        "session": None,
        "timeout": 1_000,
        "shop": "dummy",
    }
    search = await run(
        Namespace(
            **common,
            command="search",
            keyword="query",
            page=1,
            sort="relevance",
        )
    )
    detail = await run(
        Namespace(
            **common,
            command="product",
            identifier_or_url="42",
        )
    )
    assert isinstance(search, SearchPage)
    assert isinstance(detail, Product)
    assert detail.identifier == "42"


def test_jsonable_recurses_through_public_types() -> None:
    class Example(StrEnum):
        VALUE = "value"

    product = Product(
        shop="example",
        identifier="1",
        title="title",
        url="https://example.test/1",
        current_price=Decimal("12.5"),
        scraped_at=datetime(2026, 1, 2, tzinfo=UTC),
        metadata={
            "kind": Example.VALUE,
            "nested": (Decimal("2"),),
            "departure_date": date(2026, 1, 3),
        },
    )
    data = jsonable(product)
    assert data["current_price"] == "12.5"
    assert data["scraped_at"] == "2026-01-02 00:00:00+00:00"
    assert data["metadata"] == {
        "kind": "value",
        "nested": ["2"],
        "departure_date": "2026-01-03",
    }
