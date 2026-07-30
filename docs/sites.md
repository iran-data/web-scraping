# Site notes

Inspection date: 2026-07-30. The JSON reports in `docs/inspections/` were produced by
`scripts/inspect_site.py` with Chromium and are evidence, not runtime dependencies.

## Digikala

- Search URL: `/search/?q=...`; the page automatically requests
  `https://api.digikala.com/discovery/api/v2/search`.
- Pagination: `page`; response pager includes current page, total items, and total pages.
- Sort IDs observed: relevant 22, most viewed 4, newest 1, best selling 7, cheapest 20,
  most expensive 21.
- Filters: the response contains typed filter definitions. Caller-supplied API query keys are
  forwarded.
- Cards: `vertical_product_listing.data.widgets`, with `type=product`.
- Detail: the page requests `https://api.digikala.com/v2/product/{id}/`.
- CAPTCHA: none observed. The common challenge detector still applies.

## Technolife

- Search route: `/product/list/search?keywords=...`; the search box was exercised through
  Playwright to verify the navigation rather than guessing the query parameter.
- Pagination uses `page`; the embedded search contract returns 30 products and a total count.
- Observed sort values: `price-asc`, `price-desc`, `date-desc`, and `order-desc`, supplied
  through the `ordering` parameter.
- Search products are parsed from Next.js dehydrated state. Detail pages expose schema.org
  `Product`/`AggregateOffer` data and use `/product-{id}/...` routes.
- Technolife's JSON-LD labels prices `IRR`, but its visible UI presents the identical numeric
  values as تومان. The dedicated adapter follows the visible site denomination and returns IRT.
- No CAPTCHA was observed during search, sorted pagination, or detail smoke tests.

## Digikala Jet

- Search URL: `/search/?q=...`.
- Search API: `https://api.digikalajet.ir/products/search/all/`; pagination uses the response
  pager and search results include shop-specific product IDs.
- Detail API: `/shop/{shop_id}/product/{product_id}/`. Public identifiers therefore use
  `shop_id:product_id`.
- Product data is location/shop dependent. The adapter supplies a central-Tehran location
  (`35.7005, 51.3917`) by default.
- Observed sort IDs are relevance 22, newest 1, cheapest 20, and most expensive 21.
- API prices are rial and are divided by 10 when normalized to IRT.
- No CAPTCHA was observed.

## Snapp Market

- The search box navigates to `/shopping-list/general-search?query=...`.
- Search API: `https://svc.snapp.market/mobile/v3/product-vendors/search`; pagination is
  zero-based and the response includes a total count.
- Detail API: `https://svc.snapp.market/express-search/v1/pb/products/{id}`.
- Content is location-dependent. The adapter supplies the same central-Tehran location used for
  Digikala Jet and sends the site's PWA client parameters.
- Prices are already toman. Discounts are returned separately and subtracted from the original
  price.
- Only relevance ordering is currently verified. Other sort modes raise
  `UnsupportedFeatureError` instead of being silently ignored.
- No CAPTCHA was observed in the exercised search and product flows.

## Snapp Shop

- The inspected search request returned HTTP 403, consistent with an edge bot challenge.
- Use visible mode for manual completion and save storage state. Automated solving is not
  implemented.

## Torob

- Search convention: `/search/?query=...`; the first-party API is
  `https://api.torob.com/v4/base-product/search/`.
- Pagination uses zero-based `page` with `size`; verified sorting includes popularity and price.
- Detail API: `https://api.torob.com/v4/base-product/details/?prk={random_key}`.
- Product identifiers are UUID-like `random_key` values and product links use `/p/`.
- Prices are already toman. Detail normalization selects the cheapest available seller and
  retains offer-count information.
- The HTML shell may remain pending, so the adapter avoids that unnecessary navigation and uses
  the first-party JSON contract.

## Bama

- Vehicle listing route: `/car`; page numbers and native vehicle filters are query parameters.
- Listing links use `/car/detail-{code}-{slug}`. The short `/car/detail-{code}` route also works,
  allowing standalone identifier lookup.
- Search cards expose the title, year, mileage, location, asking price, and image in rendered
  semantic links. Bama's listing page currently uses an unverified infinite-scroll contract;
  page requests above 1 raise `UnsupportedFeatureError` instead of returning duplicate data.
- Detail pages expose schema.org `Product` with a nested `Car` item and stable listing code.
- The separate `/price` catalog uses `/cad/api/price/hierarchy`. It supports server-side search,
  brand-group pagination, and `MarketPrice`, `FactoryPrice`, and `AgencyPrice` filters.
- `BamaAdapter.car_prices()` and the `bama-prices` CLI command return typed `CarPrice` records
  containing the factory/market/agency classification, price change, update label, company, and
  manufacture type.
- JSON-LD labels the price `IRR`, but the rendered page shows the identical amount as تومان.
  Both advertisements and reference prices follow the visible denomination and return IRT
  without dividing by ten.
- No CAPTCHA was observed on listing or detail pages.

## Hamrah Mechanic

- Vehicle listing route: `/cars-for-sale/`; `page` is one-based and native filter query
  parameters are forwarded.
- Search results are parsed from `__NEXT_DATA__.props.pageProps.cars`, including total count,
  page size, canonical detail URL, price, offer price, year, mileage, and location.
- Detail pages expose structured `orderDetails`, gallery, and breadcrumb data in
  `__NEXT_DATA__`.
- Detail routes use `/cars-for-sale/{brand}/{model}/{order_id}/`. The numeric ID alone is not a
  complete server route, so the adapter resolves it from a preceding search; otherwise callers
  must supply the full URL.
- Prices are explicitly shown as toman and are returned as IRT.
- Neither a general free-text listing endpoint nor sort parameter was verified. Keyword matching
  is performed against each requested result page, and unsupported sorts raise
  `UnsupportedFeatureError`.
- No CAPTCHA was observed on listing or detail pages.

## Safarmarket

- Flight form route:
  `/flights/{c|a}{origin}-{c|a}{destination}/{departure}/{return|0}/{class}/...`.
  `c` means a city code and `a` means a specific airport code.
- The rendered flight flow posts to `/api/flight/v3/search`. Results contain flight legs,
  airline, schedule, capacity, stops, class, and multiple booking providers. The adapter chooses
  the lowest-priced provider. API prices are rial and are divided by 10 to return IRT.
- Train form route:
  `/trains/{origin_station_id}-{destination_station_id}/{departure}/{return|0}/...`.
  The rendered flow posts to `/api/train/v2/search`. Results include operator, train/wagon,
  schedule, seat count, compartment information, stops, and rial prices.
- Common train station IDs observed from the site's first-party station data include Tehran `1`,
  Mashhad `2`, Shiraz `3`, and Isfahan `4`. Flight examples include Tehran `THR` and Mashhad
  `MHD`.
- Safarmarket's bus form currently redirects to a Ghasedak24 route. That route returned HTTP 404
  during inspection and exposes no ticket result contract. `search_buses()` follows the
  documented hand-off but raises `UpstreamUnavailableError` clearly until the provider repairs
  it; it does not fabricate offers.
- Safarmarket's own browser application performs its normal first-party lightweight verification
  before requesting flight/train results. The adapter navigates the public result page and
  captures that response; it does not solve or bypass CAPTCHAs.

Search layouts and internal APIs can change without notice. A missing known contract raises
`LayoutChangedError`; update the corresponding fixture and parser only after a new inspection.
