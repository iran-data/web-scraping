"""Command-line interface."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path

from web_scraping.config import ScraperConfig
from web_scraping.logging import configure_logging
from web_scraping.models import CarPriceType, SortOption, TicketSearchQuery, TransportMode
from web_scraping.registry import create_adapter, create_source, supported_shops
from web_scraping.serialization import jsonable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="web-scraping")
    parser.add_argument("--visible", action="store_true", help="show the browser")
    parser.add_argument("--session", type=Path, help="Playwright storage-state file")
    parser.add_argument("--timeout", type=int, default=30_000, help="timeout in milliseconds")
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search")
    search.add_argument("shop", choices=supported_shops())
    search.add_argument("keyword")
    search.add_argument("--page", type=int, default=1)
    search.add_argument("--sort", choices=[item.value for item in SortOption], default="relevance")

    product = subparsers.add_parser("product")
    product.add_argument("shop", choices=supported_shops())
    product.add_argument("identifier_or_url")

    prices = subparsers.add_parser(
        "bama-prices", help="retrieve Bama market, factory, and agency car prices"
    )
    prices.add_argument("keyword", nargs="?", default="")
    prices.add_argument("--page", type=int, default=1)
    prices.add_argument("--page-size", type=int, default=20)
    prices.add_argument(
        "--type",
        choices=["all", *(item.value for item in CarPriceType)],
        default="all",
    )

    tickets = subparsers.add_parser(
        "tickets", help="search Safarmarket flight, train, or bus tickets"
    )
    tickets.add_argument("mode", choices=[item.value for item in TransportMode])
    tickets.add_argument("origin", help="Safarmarket city/airport/station identifier")
    tickets.add_argument("destination", help="Safarmarket city/airport/station identifier")
    tickets.add_argument("departure_date", type=date.fromisoformat, metavar="YYYY-MM-DD")
    tickets.add_argument("--return-date", type=date.fromisoformat)
    tickets.add_argument("--adults", type=int, default=1)
    tickets.add_argument("--children", type=int, default=0)
    tickets.add_argument("--infants", type=int, default=0)
    tickets.add_argument("--origin-airport", action="store_true")
    tickets.add_argument("--destination-airport", action="store_true")
    tickets.add_argument("--cabin-class", default="allclasses")
    tickets.add_argument("--exclusive-coupe", action="store_true")
    tickets.add_argument("--ticket-type", default="NORMAL")
    return parser


async def run(args: argparse.Namespace) -> object:
    config = ScraperConfig(
        headless=not args.visible,
        timeout_ms=args.timeout,
        session_path=args.session,
    )
    if args.command == "tickets":
        source = create_source("safarmarket", config)
        from web_scraping.transportation import TransportationSource

        if not isinstance(source, TransportationSource):
            raise RuntimeError("tickets requires a transportation source")
        query = TicketSearchQuery(
            mode=TransportMode(args.mode),
            origin=args.origin,
            destination=args.destination,
            departure_date=args.departure_date,
            return_date=args.return_date,
            adults=args.adults,
            children=args.children,
            infants=args.infants,
            origin_is_city=not args.origin_airport,
            destination_is_city=not args.destination_airport,
            cabin_class=args.cabin_class,
            exclusive_coupe=args.exclusive_coupe,
            ticket_type=args.ticket_type,
        )
        async with source:
            return await source.search_tickets(query)

    shop = "bama" if args.command == "bama-prices" else args.shop
    async with create_adapter(shop, config) as adapter:
        if args.command == "bama-prices":
            from web_scraping.adapters.bama import BamaAdapter

            if not isinstance(adapter, BamaAdapter):
                raise RuntimeError("bama-prices requires the Bama adapter")
            return await adapter.car_prices(
                args.keyword,
                page=args.page,
                page_size=args.page_size,
                price_type=None if args.type == "all" else CarPriceType(args.type),
            )
        if args.command == "search":
            return await adapter.search(
                args.keyword,
                page=args.page,
                sort=SortOption(args.sort),
            )
        return await adapter.get_product(args.identifier_or_url)


def main() -> None:
    configure_logging()
    args = build_parser().parse_args()
    result = asyncio.run(run(args))
    print(json.dumps(jsonable(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
