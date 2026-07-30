"""Responsible shared Playwright lifecycle, navigation, and session handling."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TypeVar

import structlog
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)
from playwright.async_api import (
    Error as PlaywrightError,
)
from playwright.async_api import (
    TimeoutError as PlaywrightTimeoutError,
)

from web_scraping.config import ScraperConfig
from web_scraping.exceptions import BotChallengeError, NavigationError

T = TypeVar("T")
_CHALLENGE_MARKERS = (
    "captcha",
    "g-recaptcha",
    "hcaptcha",
    "cf-chl-",
    "cloudflare",
    "verify you are human",
    "access denied",
    "کپچا",
    "ربات نیستید",
)


class RateLimiter:
    def __init__(self, requests_per_second: float) -> None:
        self._interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self._interval - (time.monotonic() - self._last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request = time.monotonic()


class BrowserSession:
    """Owns one browser context and applies global politeness controls."""

    def __init__(self, config: ScraperConfig) -> None:
        self.config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._limiter = RateLimiter(config.requests_per_second)
        self._logger = structlog.get_logger(__name__)

    @property
    def context(self) -> BrowserContext:
        if self._context is None:
            raise RuntimeError("BrowserSession is not started; use 'async with'")
        return self._context

    async def start(self) -> None:
        if self._context is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
        context_options: dict[str, object] = {
            "locale": self.config.locale,
            "timezone_id": self.config.timezone_id,
        }
        if self.config.user_agent:
            context_options["user_agent"] = self.config.user_agent
        session_path = self.config.session_path
        if session_path and session_path.exists():
            context_options["storage_state"] = str(session_path)
        self._context = await self._browser.new_context(**context_options)  # type: ignore[arg-type]
        self._context.set_default_timeout(self.config.timeout_ms)
        self._context.set_default_navigation_timeout(self.config.navigation_timeout_ms)

    async def new_page(self) -> Page:
        await self.start()
        return await self.context.new_page()

    async def save_session(self, path: Path | None = None) -> Path:
        target = path or self.config.session_path
        if target is None:
            raise ValueError("A session path must be configured or supplied")
        target.parent.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=str(target))
        return target

    async def close(self) -> None:
        if self._context is not None:
            if self.config.session_path is not None:
                await self.save_session()
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def navigate(self, page: Page, url: str) -> None:
        async def operation() -> None:
            response = await page.goto(url, wait_until="domcontentloaded")
            if response is not None and response.status >= 500:
                raise NavigationError(f"{url} returned HTTP {response.status}")
            await self._handle_challenge(page)

        await self.run(operation, operation_name="navigate", url=url)

    async def run(
        self,
        operation: Callable[[], Awaitable[T]],
        *,
        operation_name: str,
        url: str | None = None,
    ) -> T:
        last_error: Exception | None = None
        async with self._semaphore:
            for attempt in range(self.config.retries + 1):
                await self._limiter.wait()
                try:
                    return await operation()
                except BotChallengeError:
                    raise
                except (PlaywrightTimeoutError, PlaywrightError, NavigationError) as error:
                    last_error = error
                    if attempt >= self.config.retries:
                        break
                    delay = self.config.retry_backoff_seconds * (2**attempt)
                    delay += random.uniform(0, delay * 0.2)
                    self._logger.warning(
                        "browser_operation_retry",
                        operation=operation_name,
                        url=url,
                        attempt=attempt + 1,
                        delay_seconds=round(delay, 2),
                        error=str(error),
                    )
                    await asyncio.sleep(delay)
        raise NavigationError(
            f"{operation_name} failed after {self.config.retries + 1} attempts"
            + (f" for {url}" if url else "")
        ) from last_error

    async def _handle_challenge(self, page: Page) -> None:
        if not await self._has_challenge(page):
            return
        if self.config.headless:
            raise BotChallengeError(
                "Bot challenge detected. Re-run with headless=False, complete it manually, "
                "and configure session_path to reuse the authorized session."
            )
        self._logger.warning(
            "bot_challenge_waiting_for_manual_completion",
            url=page.url,
            timeout_seconds=self.config.challenge_wait_seconds,
        )
        deadline = time.monotonic() + self.config.challenge_wait_seconds
        while time.monotonic() < deadline:
            await asyncio.sleep(1)
            if not await self._has_challenge(page):
                if self.config.session_path:
                    await self.save_session()
                return
        raise BotChallengeError("Manual bot challenge completion timed out")

    @staticmethod
    async def _has_challenge(page: Page) -> bool:
        title, content = await asyncio.gather(page.title(), page.content())
        sample = f"{title}\n{content[:250_000]}".lower()
        return any(marker in sample for marker in _CHALLENGE_MARKERS)
