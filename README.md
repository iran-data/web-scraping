# web-scraping

Production-oriented async Playwright scraping sources for Iranian websites. The current
commerce category provides normalized product and vehicle data from:

- Digikala
- Technolife
- Snapp Market
- Digikala Jet
- Snapp Shop
- Torob
- Bama
- Hamrah Mechanic

The transportation category currently provides Safarmarket flight and train offers. Its bus
entry point is implemented, but Safarmarket's current Ghasedak24 hand-off is unavailable; see
[limitations](#limitations).

## Documentation

- [Getting started](docs/getting-started.md)
- [Python API reference](docs/api.md)
- [CLI reference](docs/cli.md)
- [Source contracts and inspection notes](docs/sites.md)
- [Production operations](docs/operations.md)
- [Testing and weekly CI](docs/testing.md)
- [Architecture](docs/architecture.md)
- [Adding a source](docs/adding-a-source.md)

The [documentation index](docs/index.md) groups these pages by user, operator, and contributor
workflows.

## Support status

| Source | Category | Search | Details | Special behavior | Live weekly |
| --- | --- | --- | --- | --- | --- |
| Digikala | Commerce | Yes | Yes | Pagination, filters, multiple sorts | Yes |
| Technolife | Commerce | Yes | Yes | Pagination and verified sorts | Yes |
| Snapp Market | Commerce | Yes | Yes | Central-Tehran inventory context | Yes |
| Digikala Jet | Commerce | Yes | Yes | Central-Tehran inventory context | Yes |
| Snapp Shop | Commerce | Blocked | Blocked | Public flow currently returns 403 | No |
| Torob | Commerce | Yes | Yes | Offer aggregation and price sorts | Yes |
| Bama | Commerce | Yes | Yes | Market/factory/agency reference prices | Yes |
| Hamrah Mechanic | Commerce | Yes | Yes | Vehicle listings and metadata | Yes |
| Safarmarket | Transportation | Flight/train | Offer details | Bus provider route broken | Yes |

“Yes” means the behavior is backed by fixture tests and an inspected contract. It is not a
guarantee of permanent upstream availability. Partial and blocked states intentionally raise
typed errors rather than returning misleading data.

The project favors first-party JSON and schema.org data. Digikala, Technolife, Digikala Jet,
Snapp Market, Torob, Bama, and Hamrah Mechanic have dedicated typed parsers backed by inspected
first-party contracts. Snapp Shop remains registered but is currently blocked by an HTTP 403
edge challenge. See [site inspection notes](docs/sites.md) and the captured inspection reports
under `docs/inspections/`.

## Architecture

The browser, session, retry, rate-limit, challenge, and registry layers are domain-neutral.
`BaseSource` owns that shared lifecycle and does not require search, product, price, or shop
methods.

Domain interfaces sit above it:

- `CommerceAdapter` defines product search, details, pagination, and commerce helpers.
- `TransportationSource` defines typed flight, train, and bus ticket search.
- Sources outside commerce use the `other` category and can define their own typed records and
  domain interface.

Each source declares a `SourceCategory` and a set of `SourceCapability` values. Generic code can
use `create_source()` and `supported_sources()`. Existing commerce callers can continue using
the backward-compatible `create_adapter()`, `supported_shops()`, and `BaseShopAdapter` names.

The production boundaries are deliberate: immutable typed records, explicit capabilities, one
adapter per website, shared responsible browser controls, fixture-backed parsers, and clear
errors for layout changes, challenges, unsupported behavior, and unavailable providers.

```python
from web_scraping import SourceCategory, create_source, supported_sources

print(supported_sources(SourceCategory.COMMERCE))

source = create_source("digikala")
print(source.source_name, source.category, source.capabilities)
```

## Install with uv

Python 3.11 or newer is required.

```bash
uv sync --all-groups
uv run playwright install chromium
```

On a minimal Linux image, also run:

```bash
uv run playwright install-deps chromium
```

For a library-only installation use `uv sync --no-dev`.

## Python API

```python
import asyncio
from pathlib import Path

from web_scraping import ScraperConfig, SortOption, create_adapter


async def main() -> None:
    config = ScraperConfig(
        headless=True,
        timeout_ms=30_000,
        retries=2,
        concurrency=3,
        requests_per_second=0.5,
        session_path=Path("playwright/.auth/digikala.json"),
    )
    async with create_adapter("digikala", config) as shop:
        page = await shop.search(
            "هدفون",
            page=1,
            sort=SortOption.CHEAPEST,
            filters={"has_selling_stock": 1},
        )
        details = await shop.get_product(page.items[0].url)
        print(details)


asyncio.run(main())
```

`iter_search()` streams normalized products across pages. `popular()` and `best_selling()` use
the site's sort mode when one is exposed. All adapters return immutable `Product` and
`SearchPage` dataclasses. Prices are normalized to Iranian toman (`IRT`), ratings to 1–5, and
timestamps to UTC.

## CLI

```bash
uv run web-scraping search digikala "گوشی سامسونگ" --page 1 --sort cheapest
uv run web-scraping product digikala 22258282
uv run web-scraping search bama "پژو"
uv run web-scraping bama-prices "پژو" --type factory
uv run web-scraping bama-prices --type market --page 1 --page-size 20
uv run web-scraping tickets flight THR MHD 2026-08-05
uv run web-scraping tickets train 1 2 2026-08-05
uv run web-scraping tickets bus 11320000 31310000 2026-08-05
uv run web-scraping product hamrahmechanic \
  "https://www.hamrah-mechanic.com/cars-for-sale/hyundai/sonatahybrid/3296021/"
uv run web-scraping --visible --session playwright/.auth/shop.json \
  search snappshop "هدفون"
```

Results are UTF-8 JSON on stdout. Structured logs go through Python logging.

### Safarmarket tickets

Use Safarmarket's identifiers: flight city/airport codes (`THR`, `MHD`), train station IDs
(`1` Tehran, `2` Mashhad, `3` Shiraz, `4` Isfahan), and bus city IDs (`11320000` Tehran,
`31310000` Mashhad). Dates supplied to Python and the CLI are Gregorian ISO dates.

```python
from datetime import date

from web_scraping import TicketSearchQuery, TransportMode, create_source
from web_scraping.transportation import TransportationSource

source = create_source("safarmarket")
assert isinstance(source, TransportationSource)
query = TicketSearchQuery(
    mode=TransportMode.FLIGHT,
    origin="THR",
    destination="MHD",
    departure_date=date(2026, 8, 5),
)
async with source:
    results = await source.search_tickets(query)
```

Prices are normalized from Safarmarket's rial API values to toman (`IRT`). Offers also include
departure/arrival times, operator, service number, availability, remaining seats, provider,
class, duration, stops, booking URL, and source-specific metadata.

### Bama reference prices

`bama-prices` reads Bama's separate new-car price catalog rather than sale advertisements.
Supported price types are `market`, `factory`, and `agency`; omit `--type` to return all three.
Prices are returned as typed `CarPrice` records in toman:

```python
from web_scraping import CarPriceType
from web_scraping.adapters.bama import BamaAdapter

async with BamaAdapter() as shop:
    prices = await shop.car_prices(
        "پژو",
        price_type=CarPriceType.FACTORY,
    )
```

## Browser sessions and challenges

Set `headless=False` (CLI: `--visible`) if a site presents a CAPTCHA, login, or location prompt.
The library waits for manual completion for `challenge_wait_seconds`, then saves Playwright
storage state when `session_path` is configured. Future runs reuse that state.

The library does not crack CAPTCHAs, call CAPTCHA-solving services, spoof browser fingerprints,
or evade access controls. In headless mode a recognized challenge raises `BotChallengeError`.
Visible mode is not a guarantee of access: stop if a site's terms or robots policy disallows the
intended use.

## Responsible operation

Defaults deliberately limit each session to three concurrent operations and one request every
two seconds. Lower these values for sensitive sites. Cache results in the calling application,
avoid repeated detail fetches, and do not collect personal data. Site terms and applicable law
remain the caller's responsibility.

## Development

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
```

Parser tests use saved first-party JSON fixtures under `tests/fixtures/`; they do not access the
network. Live tests should be marked `integration` and are opt-in. Inspection utilities:

```bash
uv run python scripts/inspect_site.py URL --output docs/inspections/site.json
uv run python scripts/capture_json_fixture.py API_URL tests/fixtures/site/name.json
```

Fixtures may contain changing catalog data. Keep them minimal where practical and never capture
cookies, authorization headers, user details, or storage state.

See [Testing and continuous integration](docs/testing.md) for test-layer expectations, fixture
policy, scheduled-failure triage, and regression-test guidance.

## Weekly website-change detection

[`.github/workflows/weekly-live-contracts.yml`](.github/workflows/weekly-live-contracts.yml)
runs every Monday at 03:17 UTC and can also be started manually from GitHub Actions. It performs:

- formatting, linting, strict type checking, and all offline tests;
- live search, detail, normalized-field, and pagination contracts for every active source;
- a separate Bama factory-price contract;
- JUnit report upload retained for 30 days.

Snapp Shop is excluded while its public flow consistently returns HTTP 403. The live suite uses
one browser operation at a time and a four-second minimum interval per source operation.

Run the same checks locally:

```bash
uv run pytest -m "not integration"
LIVE_SITE=all uv run pytest tests/integration -m integration -vv --no-cov
LIVE_SITE=digikala uv run pytest tests/integration -m integration -vv --no-cov
```

Scheduled workflows run from the repository's default branch after this workflow file is pushed
to GitHub. A contract failure makes the workflow red; GitHub notification delivery depends on
the repository watcher and Actions notification settings.

## Adding a source

1. Choose the domain model first. Do not force unrelated data into the product model.
2. Subclass `BaseSource` for a new domain, or the matching domain interface such as
   `CommerceAdapter`. Put domain-specific shared behavior in its own interface.
3. Declare `source_name`, `category`, and truthful `capabilities`.
4. Inspect navigation, pagination, filters, structured scripts, first-party endpoints, and
   challenge behavior with Playwright. Prefer stable structured contracts over generated CSS.
5. Add the source to `registry.py`, provide sanitized fixtures, and test normal, missing-value,
   and changed-layout cases.
6. Update the source documentation and run formatting, linting, strict type checking, and tests.

The full [adding-a-source guide](docs/adding-a-source.md) includes implementation standards,
minimum tests, security rules, and a review checklist.

## Limitations

- Iranian storefronts change frequently and can vary by location, account, and experiment.
- Snapp Market and Digikala Jet use a default central-Tehran location
  (`35.7005, 51.3917`) for useful inventory.
- Snapp Shop returned an edge challenge during the documented inspection.
- Supported sorting varies by site. In particular, Snapp Market currently has only verified
  relevance ordering; unsupported sort requests raise `UnsupportedFeatureError`.
- Digikala, Technolife, Digikala Jet, Snapp Market, Torob, and Bama accept bare identifiers.
  Digikala Jet identifiers use the `shop_id:product_id` form returned by search.
- Bama and Hamrah Mechanic are vehicle-listing sources. Retail-only fields such as rating and
  review count are generally unavailable; year, mileage, location, transmission, and condition
  are returned in `metadata`.
- Safarmarket flight and train searches require source-native route IDs. The bus flow currently
  raises `UpstreamUnavailableError` because Safarmarket's external provider route is broken.
- Neither vehicle site exposes a verified general free-text listing API. Keyword matching is
  therefore applied to the listings on each requested page; use `iter_search()` for multiple
  pages and pass native query filters where known.
- Hamrah Mechanic detail URLs contain brand and model slugs. A bare numeric ID works after a
  search on the same adapter instance; standalone CLI detail requests should use the full URL.

## Stability and compatibility

The package is pre-1.0. Public dataclasses, enums, factories, adapter interfaces, source names,
CLI commands, and normalized currency semantics are compatibility-sensitive. Upstream website
contracts remain inherently unstable and are monitored by weekly live tests.

Applications should persist the source name and source-native identifier together; identifiers
are not globally unique. Before upgrading, review public model and CLI changes and run your own
source-specific integration contracts.

## Security and privacy

Supported public flows do not require credentials. If an operator supplies an authenticated
Playwright session, its storage-state file is a secret. Never commit it, log it, attach it to CI
artifacts, or share it across unrelated deployments.

The library does not implement CAPTCHA cracking, third-party solving, fingerprint spoofing, or
access-control bypasses. See [Production operations](docs/operations.md) for responsible-use,
session, logging, deployment, and incident-response guidance.
