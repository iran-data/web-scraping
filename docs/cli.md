# CLI reference

## Global syntax

```text
web-scraping [--visible] [--session PATH] [--timeout MS] COMMAND ...
```

Global options must appear before the command:

- `--visible`: launch a visible Chromium browser.
- `--session PATH`: load and save Playwright storage state.
- `--timeout MS`: action timeout; default `30000`.

Run through the locked environment:

```bash
uv run web-scraping --help
uv run web-scraping COMMAND --help
```

Output is pretty-printed UTF-8 JSON on stdout.

## Product search

```text
web-scraping search SHOP KEYWORD [--page N] [--sort SORT]
```

Example:

```bash
uv run web-scraping search digikala "گوشی سامسونگ" --page 1 --sort cheapest
```

Sort names are `relevance`, `newest`, `cheapest`, `most_expensive`, `most_popular`, and
`best_selling`. Availability varies by source; unsupported modes fail clearly.

## Product details

```text
web-scraping product SHOP IDENTIFIER_OR_URL
```

```bash
uv run web-scraping product digikala 22258282
uv run web-scraping product hamrahmechanic \
  "https://www.hamrah-mechanic.com/cars-for-sale/hyundai/sonatahybrid/3296021/"
```

Some sources require the full URL or a composite search-result identifier. See
[Source support](sites.md).

## Bama reference prices

```text
web-scraping bama-prices [KEYWORD] [--page N] [--page-size N]
                         [--type all|market|factory|agency]
```

```bash
uv run web-scraping bama-prices "پژو" --type factory
uv run web-scraping bama-prices --type market --page 1 --page-size 20
```

This accesses Bama's reference-price catalog, not used-car advertisements.

## Transportation tickets

```text
web-scraping tickets MODE ORIGIN DESTINATION YYYY-MM-DD
    [--return-date YYYY-MM-DD]
    [--adults N] [--children N] [--infants N]
    [--origin-airport] [--destination-airport]
    [--cabin-class VALUE]
    [--exclusive-coupe]
    [--ticket-type VALUE]
```

Flight city search:

```bash
uv run web-scraping tickets flight THR MHD 2026-08-05 \
  --adults 2 --children 1
```

Use `--origin-airport` or `--destination-airport` when a flight endpoint is an airport rather
than a city.

Train search:

```bash
uv run web-scraping tickets train 1 2 2026-08-05
uv run web-scraping tickets train 1 3 2026-08-05 --exclusive-coupe
```

Bus search:

```bash
uv run web-scraping tickets bus 11320000 31310000 2026-08-05
```

Bus mode uses Safar724. Origin and destination may be Safar724 city codes, English slugs, or
exact Persian city names:

```bash
uv run web-scraping tickets bus tehran mashhad 2026-08-14
uv run web-scraping tickets bus تهران مشهد 2026-08-14
```

The adapter resolves the inputs against Safar724's public city catalog before navigating its
normal rendered route page.

## Challenges and sessions

```bash
uv run web-scraping \
  --visible \
  --session playwright/.auth/digikala.json \
  search digikala "لپ تاپ"
```

Storage-state files may contain credentials or cookies. Keep them outside source control and
limit filesystem permissions in production.

## Exit behavior

Successful commands write JSON and exit zero. Invalid arguments are rejected by `argparse`.
Runtime exceptions produce a non-zero exit. Applications that need stable error envelopes should
call the Python API and map typed exceptions to their own protocol.
