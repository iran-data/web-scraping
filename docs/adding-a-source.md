# Adding a source

This project is organized by source and domain, not by an assumption that every website is a
shop.

## 1. Choose or define the domain

Use:

- `CommerceAdapter` for normalized products/listings;
- `TransportationSource` for passenger tickets;
- `BaseSource` for a new domain such as news or government data.

When introducing a domain, create typed domain models and a small public interface. Do not put
unrelated optional fields into `Product` or `TicketOffer`. Add a new `SourceCategory` only when a
real source needs it.

## 2. Inspect with Playwright

Record:

- canonical landing/search/detail URLs;
- user navigation and form behavior;
- first-party requests and response shapes;
- identifiers and URL construction;
- pagination, sorting, and filter semantics;
- structured data (`JSON-LD`, Next.js state, embedded JSON);
- currency denomination and visible labels;
- location/account dependencies;
- empty, unavailable, and sold-out states;
- CAPTCHA, login, consent, and external-provider behavior.

Prefer a real rendered flow. Do not infer an endpoint from a bundle and call it production-ready
without observing the website use it.

## 3. Define truthful capabilities

Add only capabilities verified in the current implementation. Unsupported operations should
raise `UnsupportedFeatureError`. Broken linked providers should raise
`UpstreamUnavailableError`, and changed structured contracts should raise
`LayoutChangedError`.

## 4. Implement the adapter

Place one concrete class under `src/web_scraping/adapters/`. It should:

- declare a stable registry/source name, category, and capabilities;
- use `BrowserSession` for rate limits, retries, and lifecycle;
- prefer first-party JSON, JSON-LD, stable semantic links, and stable attributes;
- normalize URLs, Persian text/digits, missing values, prices, and timestamps;
- close every page in `finally`;
- avoid unnecessary navigation or detail requests;
- return only typed public records.

Parser methods should accept mappings or fixture text independently of Playwright. This keeps
most testing fast and deterministic.

## 5. Register the source

Add it to `_SOURCES` in `registry.py`.

- Domain-neutral callers discover it through `supported_sources()`.
- Commerce sources also appear in `supported_shops()`.
- Non-commerce sources must be rejected by `create_adapter()`.

Export public models/interfaces from `web_scraping.__init__` when users need them.

## 6. Add fixtures and tests

Minimum coverage:

- registry/category/capability contract;
- URL/request construction;
- representative successful parse;
- IRR/IRT and missing-value behavior;
- wrong/missing structural fields;
- availability and pagination boundaries;
- mocked browser error behavior where practical;
- one low-volume live contract.

Fixture files must be sanitized and minimal. Never save storage state, request headers,
authorization material, personal details, or reusable booking links.

## 7. Document it

Update:

- README support summary and examples;
- `docs/sites.md` inspection contract and limitations;
- API/CLI reference if the public surface changed;
- weekly live test selection;
- architecture documentation for a new domain.

State partial support explicitly. A documented upstream failure is better than a misleading
“supported” badge.

## 8. Verify

```bash
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest -m "not integration"
LIVE_SITE=new-source uv run pytest tests/integration -m integration -vv --no-cov
```

## Review checklist

- [ ] Public names and return types are stable and typed.
- [ ] Currency units match the visible/source contract.
- [ ] Every navigation/page is closed.
- [ ] Retries do not retry deterministic parse failures.
- [ ] No CAPTCHA bypass or access-control evasion exists.
- [ ] Rate limits remain responsible.
- [ ] Layout changes produce actionable messages.
- [ ] Tests include sanitized fixtures and negative cases.
- [ ] Live checks are low-volume and non-destructive.
- [ ] Documentation lists identifiers, limitations, and operational requirements.
