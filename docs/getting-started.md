# Getting started

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/)
- Chromium installed through Playwright
- Network access to the selected public website

## Install

Clone the repository and create the locked development environment:

```bash
uv sync --all-groups --locked
uv run playwright install chromium
```

On minimal Linux hosts, install Playwright's system libraries too:

```bash
uv run playwright install --with-deps chromium
```

For a runtime-only environment:

```bash
uv sync --no-dev --locked
uv run playwright install chromium
```

Do not install Playwright's browser with a different Python environment. `uv run playwright`
ensures the executable and Python package use the same environment.

## Verify the installation

```bash
uv run python -c "import web_scraping; print(web_scraping.supported_sources())"
uv run web-scraping --help
```

The source list should include `safarmarket` alongside the commerce sources.

## First product search

```python
import asyncio

from web_scraping import ScraperConfig, create_adapter


async def main() -> None:
    config = ScraperConfig(requests_per_second=0.5)
    async with create_adapter("digikala", config) as shop:
        results = await shop.search("گوشی سامسونگ", page=1)
        for product in results.items[:5]:
            print(product.title, product.current_price, product.currency)


asyncio.run(main())
```

The async context manager starts Chromium and always closes the browser it owns. Reuse one
adapter or shared browser session for a batch instead of creating a browser per item.

## First transportation search

Safarmarket uses source-native identifiers. In this example, `THR` and `MHD` are Tehran and
Mashhad city codes:

```python
import asyncio
from datetime import date

from web_scraping import (
    TicketSearchQuery,
    TransportMode,
    TransportationSource,
    create_source,
)


async def main() -> None:
    source = create_source("safarmarket")
    assert isinstance(source, TransportationSource)
    query = TicketSearchQuery(
        mode=TransportMode.FLIGHT,
        origin="THR",
        destination="MHD",
        departure_date=date(2026, 8, 5),
    )
    async with source:
        result = await source.search_tickets(query)
        for offer in result.items:
            print(offer.operator, offer.departure_at, offer.price, offer.currency)


asyncio.run(main())
```

Use a future date when running this example. See [Source support](sites.md#safarmarket) for
known IDs and the bus limitation.

## First CLI searches

```bash
uv run web-scraping search digikala "هدفون" --page 1 --sort cheapest
uv run web-scraping product digikala 22258282
uv run web-scraping tickets flight THR MHD 2026-08-05
uv run web-scraping tickets train 1 2 2026-08-05
```

All command results are JSON encoded as UTF-8.

## Visible mode and saved sessions

If a site asks for manual interaction:

```bash
uv run web-scraping \
  --visible \
  --session playwright/.auth/source.json \
  search snappshop "هدفون"
```

Complete the challenge yourself. The browser storage state is saved on shutdown and reused on
the next run. Never commit `playwright/.auth/`; it can contain authorization material.

## Common installation failures

`Executable doesn't exist` means Chromium has not been installed:

```bash
uv run playwright install chromium
```

Missing Linux shared-library errors require:

```bash
uv run playwright install-deps chromium
```

Navigation failures may mean the source is unavailable, the network blocks it, or its layout has
changed. See [Troubleshooting and incident response](operations.md#incident-response).
