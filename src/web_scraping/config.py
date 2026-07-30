"""Runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScraperConfig:
    headless: bool = True
    timeout_ms: int = 30_000
    navigation_timeout_ms: int = 45_000
    retries: int = 2
    retry_backoff_seconds: float = 0.75
    concurrency: int = 3
    requests_per_second: float = 0.5
    user_agent: str | None = None
    locale: str = "fa-IR"
    timezone_id: str = "Asia/Tehran"
    session_path: Path | None = None
    challenge_wait_seconds: float = 180.0

    def __post_init__(self) -> None:
        if self.timeout_ms <= 0 or self.navigation_timeout_ms <= 0:
            raise ValueError("timeouts must be positive")
        if self.retries < 0:
            raise ValueError("retries cannot be negative")
        if self.retry_backoff_seconds < 0:
            raise ValueError("retry_backoff_seconds cannot be negative")
        if self.concurrency < 1:
            raise ValueError("concurrency must be at least 1")
        if self.requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        if self.challenge_wait_seconds <= 0:
            raise ValueError("challenge_wait_seconds must be positive")
