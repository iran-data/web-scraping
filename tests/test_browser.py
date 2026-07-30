from unittest.mock import AsyncMock

import pytest
from playwright.async_api import Error as PlaywrightError

from web_scraping.browser import BrowserSession, RateLimiter
from web_scraping.config import ScraperConfig
from web_scraping.exceptions import BotChallengeError, NavigationError


@pytest.mark.asyncio
async def test_challenge_detection_with_mocked_page() -> None:
    page = AsyncMock()
    page.title.return_value = "Verify you are human"
    page.content.return_value = "<html><body>captcha</body></html>"
    assert await BrowserSession._has_challenge(page)


@pytest.mark.asyncio
async def test_rate_limiter_can_be_used() -> None:
    limiter = RateLimiter(1_000)
    await limiter.wait()
    await limiter.wait()


@pytest.mark.asyncio
async def test_browser_operation_retries_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = BrowserSession(ScraperConfig(retries=2, requests_per_second=1_000))
    session._limiter.wait = AsyncMock()  # type: ignore[method-assign]
    monkeypatch.setattr("web_scraping.browser.asyncio.sleep", AsyncMock())
    operation = AsyncMock(side_effect=[PlaywrightError("temporary"), "ok"])

    result = await session.run(operation, operation_name="test", url="https://example.test")

    assert result == "ok"
    assert operation.await_count == 2


@pytest.mark.asyncio
async def test_browser_operation_exhaustion_preserves_cause() -> None:
    session = BrowserSession(ScraperConfig(retries=0, requests_per_second=1_000))
    session._limiter.wait = AsyncMock()  # type: ignore[method-assign]
    operation = AsyncMock(side_effect=PlaywrightError("broken"))

    with pytest.raises(NavigationError, match="failed after 1 attempts") as caught:
        await session.run(operation, operation_name="test", url="https://example.test")
    assert isinstance(caught.value.__cause__, PlaywrightError)


@pytest.mark.asyncio
async def test_headless_challenge_raises_clear_error() -> None:
    session = BrowserSession(ScraperConfig(headless=True))
    page = AsyncMock()
    session._has_challenge = AsyncMock(return_value=True)  # type: ignore[method-assign]
    with pytest.raises(BotChallengeError, match="headless=False"):
        await session._handle_challenge(page)


@pytest.mark.asyncio
async def test_visible_challenge_can_be_completed_manually(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = BrowserSession(
        ScraperConfig(headless=False, challenge_wait_seconds=5, session_path=None)
    )
    page = AsyncMock()
    session._has_challenge = AsyncMock(  # type: ignore[method-assign]
        side_effect=[True, False]
    )
    monkeypatch.setattr("web_scraping.browser.asyncio.sleep", AsyncMock())
    await session._handle_challenge(page)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"concurrency": 0},
        {"retries": -1},
        {"retry_backoff_seconds": -0.1},
        {"timeout_ms": 0},
        {"navigation_timeout_ms": 0},
        {"requests_per_second": 0},
        {"challenge_wait_seconds": 0},
    ],
)
def test_invalid_config(kwargs: dict[str, int | float]) -> None:
    with pytest.raises(ValueError):
        ScraperConfig(**kwargs)  # type: ignore[arg-type]
