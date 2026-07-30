"""Capture a JSON endpoint through a Playwright browser context."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def capture(url: str, output: Path) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(locale="fa-IR")
        response = await context.request.get(url, timeout=60_000)
        if not response.ok:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        data = await response.json()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(  # noqa: ASYNC240 - one small developer-only fixture write
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    asyncio.run(capture(args.url, args.output))


if __name__ == "__main__":
    main()
