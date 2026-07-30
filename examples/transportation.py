"""Search Safarmarket flight offers with the domain-neutral source factory."""

import asyncio
from datetime import date, timedelta

from web_scraping import (
    TicketSearchQuery,
    TransportationSource,
    TransportMode,
    create_source,
)


async def main() -> None:
    source = create_source("safarmarket")
    if not isinstance(source, TransportationSource):
        raise RuntimeError("safarmarket is expected to be a transportation source")
    query = TicketSearchQuery(
        mode=TransportMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date.today() + timedelta(days=14),
    )
    async with source:
        result = await source.search_tickets(query)
        for offer in result.items[:5]:
            print(
                offer.operator,
                offer.service_number,
                offer.departure_at,
                offer.price,
                offer.currency,
            )


if __name__ == "__main__":
    asyncio.run(main())
