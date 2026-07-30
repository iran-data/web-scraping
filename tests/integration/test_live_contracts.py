"""Low-volume live contracts for detecting upstream website changes."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from web_scraping import (
    Product,
    ScraperConfig,
    TicketSearchQuery,
    TransportMode,
    create_adapter,
    create_source,
)


@dataclass(frozen=True, slots=True)
class LiveCase:
    source: str
    keyword: str


# Snapp Shop is intentionally excluded while its public flow returns HTTP 403.
LIVE_CASES = (
    LiveCase("digikala", "گوشی"),
    LiveCase("technolife", "گوشی"),
    LiveCase("digikalajet", "شیر"),
    LiveCase("snappmarket", "شیر"),
    LiveCase("torob", "موبایل"),
    LiveCase("bama", "پژو"),
    LiveCase("hamrahmechanic", "هیوندای"),
)


def selected_cases() -> tuple[LiveCase, ...]:
    selected = os.getenv("LIVE_SITE")
    if not selected:
        return ()
    if selected == "all":
        return LIVE_CASES
    return tuple(case for case in LIVE_CASES if case.source == selected)


def assert_product_contract(product: Product, *, source: str) -> None:
    assert product.shop == source
    assert product.identifier.strip()
    assert product.title.strip()
    assert product.url.startswith(("http://", "https://"))
    assert product.currency == "IRT"
    assert product.current_price is None or product.current_price >= 0
    assert product.original_price is None or product.original_price >= 0
    assert product.rating is None or 1 <= product.rating <= 5
    assert product.review_count is None or product.review_count >= 0
    assert datetime.now(UTC) - product.scraped_at < timedelta(minutes=5)


@pytest.mark.integration
@pytest.mark.parametrize("case", selected_cases(), ids=lambda case: case.source)
async def test_live_search_pagination_and_detail_contract(case: LiveCase) -> None:
    """Exercise only the public adapter contract with deliberately low request volume."""
    config = ScraperConfig(
        headless=True,
        timeout_ms=45_000,
        navigation_timeout_ms=60_000,
        retries=2,
        concurrency=1,
        requests_per_second=0.25,
    )
    async with create_adapter(case.source, config) as source:
        first_page = await source.search(case.keyword, page=1)
        assert first_page.page == 1
        assert first_page.items, f"{case.source} returned no results for {case.keyword!r}"
        assert first_page.next_page in (None, 2)
        for product in first_page.items:
            assert_product_contract(product, source=case.source)

        first = first_page.items[0]
        # Search may return a canonical URL or a source-specific composite ID. The ID
        # is the one detail contract guaranteed consistently across commerce sources.
        detail = await source.get_product(first.identifier)
        assert_product_contract(detail, source=case.source)
        assert detail.identifier == first.identifier

        if first_page.has_next:
            second_page = await source.search(case.keyword, page=2)
            assert second_page.page == 2
            assert second_page.next_page in (None, 3)
            for product in second_page.items:
                assert_product_contract(product, source=case.source)
            if second_page.items:
                first_ids = {product.identifier for product in first_page.items}
                second_ids = {product.identifier for product in second_page.items}
                assert first_ids != second_ids, (
                    f"{case.source} pagination returned the same identifiers on pages 1 and 2"
                )


@pytest.mark.integration
async def test_live_bama_reference_price_contract() -> None:
    if os.getenv("LIVE_SITE") not in {"all", "bama"}:
        pytest.skip("set LIVE_SITE=all or LIVE_SITE=bama")

    from web_scraping.adapters.bama import BamaAdapter
    from web_scraping.models import CarPriceType

    config = ScraperConfig(
        headless=True,
        navigation_timeout_ms=60_000,
        retries=2,
        concurrency=1,
        requests_per_second=0.25,
    )
    async with BamaAdapter(config) as bama:
        prices = await bama.car_prices(
            "پژو",
            page=1,
            page_size=3,
            price_type=CarPriceType.FACTORY,
        )
    assert prices.items
    assert prices.page == 1
    assert prices.last_updated
    for price in prices.items:
        assert price.brand
        assert price.model
        assert price.price > 0
        assert price.currency == "IRT"
        assert price.price_type == CarPriceType.FACTORY


@pytest.mark.integration
@pytest.mark.parametrize(
    ("mode", "origin", "destination"),
    [
        (TransportMode.FLIGHT, "THR", "MHD"),
        (TransportMode.TRAIN, "1", "2"),
    ],
)
async def test_live_safarmarket_ticket_contract(
    mode: TransportMode, origin: str, destination: str
) -> None:
    if os.getenv("LIVE_SITE") not in {"all", "safarmarket"}:
        pytest.skip("set LIVE_SITE=all or LIVE_SITE=safarmarket")

    from web_scraping.transportation import TransportationSource

    config = ScraperConfig(
        headless=True,
        timeout_ms=45_000,
        navigation_timeout_ms=60_000,
        retries=2,
        concurrency=1,
        requests_per_second=0.25,
    )
    source = create_source("safarmarket", config)
    assert isinstance(source, TransportationSource)
    query = TicketSearchQuery(
        mode=mode,
        origin=origin,
        destination=destination,
        departure_date=(datetime.now(UTC) + timedelta(days=14)).date(),
    )
    async with source:
        result = await source.search_tickets(query)

    assert result.query == query
    assert result.search_url.startswith("https://safarmarket.com/")
    assert result.items
    assert result.total == len(result.items)
    for offer in result.items:
        assert offer.source == "safarmarket"
        assert offer.mode == mode
        assert offer.identifier
        assert offer.origin
        assert offer.destination
        assert offer.price > 0
        assert offer.currency == "IRT"
        assert datetime.now(UTC) - offer.scraped_at < timedelta(minutes=5)
