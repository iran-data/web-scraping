# Testing and continuous integration

## Test layers

### Model and normalization tests

These verify validation, Persian/Arabic digit normalization, text cleanup, URL resolution,
ratings, and rial-to-toman conversion.

### Fixture parser tests

Sanitized JSON/HTML fixtures under `tests/fixtures/` exercise stable parsers without network
access. Tests cover valid data, missing optional values, malformed contracts, and
`LayoutChangedError` behavior.

### Mocked browser/API tests

Browser lifecycle, retries, rate limits, challenges, and adapter request contracts are mocked
where practical. These tests should verify request construction and error mapping without
duplicating Playwright itself.

### Live contracts

Low-volume Playwright tests exercise public source behavior. They are intentionally separate
because upstream availability and catalog contents are not deterministic.

## Local quality gates

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest -m "not integration"
```

The configured coverage floor is 70%. Coverage is a regression guard, not a substitute for
meaningful changed-layout and boundary tests.

Run live contracts:

```bash
LIVE_SITE=all uv run pytest tests/integration -m integration -vv --no-cov
LIVE_SITE=digikala uv run pytest tests/integration -m integration -vv --no-cov
LIVE_SITE=safarmarket uv run pytest tests/integration -m integration -vv --no-cov
```

Use a specific source while developing. `LIVE_SITE=all` is intended for release checks and the
weekly workflow.

## Weekly workflow

`.github/workflows/weekly-live-contracts.yml` runs every Monday at 03:17 UTC and supports manual
dispatch.

The workflow:

1. installs Python and dependencies from `uv.lock`;
2. checks formatting, linting, strict typing, and offline tests;
3. installs Chromium with system dependencies;
4. runs active live source contracts at low concurrency;
5. uploads a JUnit report for 30 days, even when tests fail.

Snapp Shop is excluded while its public flow returns HTTP 403. Safarmarket flight/train and
Safar724 bus contracts are included.

## Interpreting weekly failures

- A parser/layout assertion usually indicates an upstream schema change.
- Identical page-one/page-two IDs indicate broken pagination.
- An empty result may be catalog/date/location dependent; reproduce with another known query
  before changing code.
- HTTP/timeouts across several sources often indicate runner networking or regional access.
- One source consistently failing while others pass usually indicates a source incident or
  contract change.

Do not automatically update fixtures from a failed scheduled run. Inspect and sanitize the new
contract first.

## Fixture policy

Fixtures must:

- come from a verified public browser/API flow;
- be reduced to fields required by parser tests;
- preserve enough structure to detect layout changes;
- remove cookies, headers, tokens, user IDs, booking tokens, and personal data;
- document whether prices are IRR or IRT.

Capture helpers:

```bash
uv run python scripts/inspect_site.py URL --output docs/inspections/source.json
uv run python scripts/capture_json_fixture.py API_URL tests/fixtures/source/name.json
```

Direct endpoint capture works only for endpoints that do not require a rendered flow. For
Safarmarket, inspect the browser-initiated response rather than replaying its verification
request manually.

## Adding regression cases

For each bug:

1. reduce the failing response to a safe fixture;
2. add a test that fails before the fix;
3. implement the smallest parser correction;
4. add missing-value and wrong-type cases when relevant;
5. run the focused live contract once.
