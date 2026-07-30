# Contributing

Thank you for improving `web-scraping`.

Start with:

- [Architecture](docs/architecture.md)
- [Adding a source](docs/adding-a-source.md)
- [Testing and CI](docs/testing.md)
- [Production operations](docs/operations.md)

## Development setup

```bash
uv sync --all-groups --locked
uv run playwright install chromium
```

Before submitting a change:

```bash
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest -m "not integration"
```

Run a focused live contract only when the affected source requires it:

```bash
LIVE_SITE=SOURCE uv run pytest tests/integration -m integration -vv --no-cov
```

Keep changes focused. Preserve unrelated work in the repository, add a regression fixture for
parser fixes, and update documentation whenever public behavior or support status changes.

Do not commit browser sessions, credentials, cookies, private user data, reusable booking
tokens, or unsanitized response captures. Do not add CAPTCHA solving, fingerprint spoofing, or
access-control bypasses.
