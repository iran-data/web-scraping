# Production operations

## Responsible request policy

Scraping authorization is deployment-specific. Before enabling a source:

1. Review the website's current terms, robots policy, and applicable law.
2. Collect only data required for the documented purpose.
3. Avoid personal, account-only, or access-controlled data.
4. Cache results and deduplicate detail requests.
5. Use low concurrency and rate limits; increase them only with evidence and permission.

The defaults allow three simultaneous operations and 0.5 operations per second per browser
session. For scheduled monitoring, prefer `concurrency=1` and `requests_per_second=0.25`.

## Browser lifecycle

Use the async context manager:

```python
async with create_source("safarmarket", config) as source:
    ...
```

It starts the browser lazily and closes owned pages, contexts, and Chromium. A process that exits
without closing may leave Chromium processes or an incomplete session file.

Share one `BrowserSession` across compatible adapters when an application needs coordinated
limits and browser state. When a session is injected into a source, the caller owns its
lifecycle.

## Sessions and secrets

`session_path` stores Playwright browser state. Treat it as a secret:

- never commit it;
- restrict read/write access to the service account;
- encrypt it at rest where required;
- rotate/delete it when authorization changes;
- do not upload it as a test artifact.

The repository ignores `playwright/.auth/` by default.

## CAPTCHA and bot challenges

The package detects common challenge markers.

- Headless mode raises `BotChallengeError`.
- Visible mode waits up to `challenge_wait_seconds` for manual completion.
- Successful manual completion can be saved in `session_path`.

The library does not crack CAPTCHAs, call solving services, spoof fingerprints, or bypass access
controls. A visible browser is a manual recovery path, not permission to evade a site's policy.

## Retries and timeouts

Navigation, Playwright, and retryable browser errors use exponential backoff with small jitter.
`retries=2` means three total attempts. Parsing and layout errors are not retried because the same
payload will normally fail again.

Set:

- `timeout_ms` for selectors and ordinary Playwright actions;
- `navigation_timeout_ms` for page navigation and captured API responses;
- `retry_backoff_seconds` for retry spacing.

Avoid very high retry counts. They increase load during an upstream incident and delay useful
alerts.

## Structured logging

Call `configure_logging()` once at application startup. Logs are JSON and include timestamp,
level, event name, URL, operation, attempt, delay, and error where applicable.

```python
import logging

from web_scraping.logging import configure_logging

configure_logging(logging.INFO)
```

Send stdout/stderr to the deployment's normal log collector. Do not add response bodies,
cookies, authorization headers, or storage state to logs.

Useful production metrics around the library include:

- searches and details by source/outcome;
- operation duration and retry count;
- `LayoutChangedError` count;
- bot-challenge count;
- empty-result rate for normally active queries;
- age of the last successful live contract.

## Deployment

Pin the repository lockfile and install Chromium during the image build:

```dockerfile
RUN uv sync --no-dev --locked
RUN uv run playwright install --with-deps chromium
```

Run as a non-root user when possible. Provide enough shared memory for Chromium; container
platforms with very small `/dev/shm` may cause unexplained browser crashes.

Do not expose the CLI directly to untrusted input without validation. URLs, filter values,
passenger counts, page limits, and workload size should be bounded by the calling service.

## Incident response

### `LayoutChangedError`

1. Reproduce once with a low-volume visible inspection.
2. Compare the current first-party JSON/structured data with the saved fixture.
3. Determine whether this is a rollout, location/account variation, or permanent change.
4. Update the parser and sanitized fixture together.
5. Run offline and focused live contracts before release.

Do not replace a structured parser with a fragile visual selector just to make the alert green.

### `NavigationError`

Check website availability, DNS/network policy, response status, timeout settings, and whether a
challenge page appeared. Retry later rather than creating a high-frequency retry loop.

### `BotChallengeError`

Use visible mode only if manual completion is permitted, save the resulting session securely,
and lower request volume. Do not automate challenge solving.

### `UpstreamUnavailableError`

The primary source depends on another provider that is not serving the required flow. Preserve
the error as a separate operational state; do not treat it as an empty search.

## Release checklist

- `uv lock --check`
- formatting, linting, strict typing, and offline tests pass;
- focused live contracts pass for changed sources;
- fixtures contain no secrets or personal data;
- README, source notes, API, and limitation tables are current;
- lockfile and source changes are reviewed together.
