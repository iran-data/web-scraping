# Python API reference

## Factories and discovery

### `supported_sources(category=None)`

Returns registered source names, sorted alphabetically. Pass a `SourceCategory` to filter them.

```python
from web_scraping import SourceCategory, supported_sources

supported_sources()
supported_sources(SourceCategory.COMMERCE)
supported_sources(SourceCategory.TRANSPORTATION)
```

### `create_source(name, config=None)`

Creates any registered `BaseSource`. Use this in domain-neutral applications.

### `supported_shops()` and `create_adapter(name, config=None)`

Compatibility APIs for commerce sources. `create_adapter()` returns a `CommerceAdapter` and
rejects transportation or future non-commerce sources.

## Source categories

- `commerce`: product, vehicle listing, and price-catalog sources.
- `transportation`: passenger ticket sources.
- `other`: sources whose domain does not yet justify a dedicated category.

Categories are intentionally broad. A future news or government source can define its own typed
interface without changing commerce or transportation models.

## Commerce interface

Every `CommerceAdapter` implements:

```python
await adapter.search(
    keyword,
    page=1,
    sort=SortOption.RELEVANCE,
    filters=None,
) -> SearchPage

await adapter.get_product(identifier_or_url) -> Product
```

It also supplies:

```python
adapter.iter_search(keyword, start_page=1, max_pages=None, sort=..., filters=...)
await adapter.popular(limit=20)
await adapter.best_selling(limit=20)
```

Sorting and filters remain source-specific. Unsupported behavior raises
`UnsupportedFeatureError`; the library does not silently ignore a requested sort.

### `Product`

Immutable normalized fields:

| Field | Type | Notes |
| --- | --- | --- |
| `shop` | `str` | Stable source registry name |
| `identifier` | `str` | Source-native stable identifier |
| `title` | `str` | Normalized Persian text and whitespace |
| `url` | `str` | Absolute canonical or detail URL |
| `image_url` | `str \| None` | Absolute when available |
| `current_price` | `Decimal \| None` | Toman |
| `original_price` | `Decimal \| None` | Toman, before discount |
| `discount_percentage` | `Decimal \| None` | Numeric percentage |
| `currency` | `str` | `IRT` |
| `availability` | `Availability` | Stock state |
| `seller`, `brand` | `str \| None` | Source-dependent |
| `rating` | `float \| None` | Normalized to 1–5 |
| `review_count` | `int \| None` | Non-negative |
| `popularity` | `str \| None` | Purchase/popularity label |
| `scraped_at` | `datetime` | UTC |
| `metadata` | `Mapping[str, Any]` | Domain/source-specific extras |

`SearchPage` contains `items`, `page`, `has_next`, `total`, and `next_page`.

### Bama reference prices

`BamaAdapter.car_prices()` returns a `CarPricePage` independently of vehicle advertisements:

```python
from web_scraping import CarPriceType
from web_scraping.adapters.bama import BamaAdapter

async with BamaAdapter() as bama:
    result = await bama.car_prices(
        "پژو",
        page=1,
        page_size=20,
        price_type=CarPriceType.FACTORY,
    )
```

`CarPriceType` supports `MARKET`, `FACTORY`, and `AGENCY`.

## Transportation interface

`TransportationSource.search_tickets(query)` dispatches by `TransportMode`. The explicit
`search_flights`, `search_trains`, and `search_buses` methods are also public.

### `TicketSearchQuery`

| Field | Default | Meaning |
| --- | --- | --- |
| `mode` | required | `flight`, `train`, or `bus` |
| `origin`, `destination` | required | Source-native code or ID |
| `departure_date` | required | Gregorian `date` |
| `return_date` | `None` | Optional Gregorian return date |
| `adults` | `1` | Must be at least one |
| `children`, `infants` | `0` | Non-negative |
| `origin_is_city`, `destination_is_city` | `True` | Flight city versus airport code |
| `cabin_class` | `allclasses` | Safarmarket route value |
| `exclusive_coupe` | `False` | Train compartment request |
| `ticket_type` | `NORMAL` | Safarmarket train ticket type |

The model rejects empty/equal endpoints, invalid passenger counts, and return dates before
departure.

### `TicketOffer`

Each immutable offer includes source, mode, identifier, route, departure and arrival timestamps,
operator, service number, toman price, original price, availability, remaining seats, duration,
provider, booking URL, class, stop count, UTC scrape time, and source-specific metadata.

`TicketSearchResult` contains the original query, offers, search URL, total, and scrape time.

## Configuration

`ScraperConfig` is immutable:

| Option | Default | Description |
| --- | ---: | --- |
| `headless` | `True` | Run without a visible browser |
| `timeout_ms` | `30000` | Playwright action timeout |
| `navigation_timeout_ms` | `45000` | Navigation/response timeout |
| `retries` | `2` | Additional retry attempts |
| `retry_backoff_seconds` | `0.75` | Exponential-backoff base |
| `concurrency` | `3` | Maximum simultaneous browser operations |
| `requests_per_second` | `0.5` | Per-session operation rate |
| `user_agent` | `None` | Optional explicit user agent |
| `locale` | `fa-IR` | Browser locale |
| `timezone_id` | `Asia/Tehran` | Browser timezone |
| `session_path` | `None` | Playwright storage-state path |
| `challenge_wait_seconds` | `180` | Visible manual-completion window |

Invalid non-positive timeouts/rates and invalid retry/concurrency values fail immediately.

## Exceptions

Catch the narrowest exception useful to your application:

| Exception | Meaning |
| --- | --- |
| `ScraperError` | Base package exception |
| `NavigationError` | Browser/API operation failed after retries |
| `ParsingError` | Structured content could not be parsed |
| `LayoutChangedError` | A verified upstream contract no longer matches |
| `ProductNotFoundError` | Requested product is absent |
| `UnsupportedFeatureError` | Source does not support the requested operation |
| `BotChallengeError` | Manual challenge completion is required or timed out |
| `UpstreamUnavailableError` | A required linked provider is unavailable |

Validation errors such as an invalid page or passenger count use `ValueError`.

## Serialization

Public records are dataclasses. For JSON-safe output, including `Decimal`, enum, and datetime
conversion:

```python
import json

from web_scraping.serialization import jsonable

payload = json.dumps(jsonable(result), ensure_ascii=False)
```
