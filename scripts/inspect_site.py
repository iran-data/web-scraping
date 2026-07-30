"""Developer utility: inspect page structure without mutating or interacting with it."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


async def inspect(url: str, output: Path | None) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(locale="fa-IR")
        responses: list[dict[str, object]] = []

        def record_response(response: object) -> None:
            url_value = getattr(response, "url", "")
            if any(token in url_value for token in ("api", "search", "product")):
                responses.append(
                    {
                        "url": url_value,
                        "status": getattr(response, "status", None),
                        "content_type": getattr(response, "headers", {}).get("content-type"),
                    }
                )

        page.on("response", record_response)
        response = await page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        await page.wait_for_timeout(5_000)
        scripts = await page.locator(
            'script[type="application/ld+json"], script#__NEXT_DATA__'
        ).all_text_contents()
        links = await page.locator('a[href*="/product/"]').evaluate_all(
            "(nodes) => nodes.slice(0, 5).map(n => n.href)"
        )
        report = {
            "requested_url": url,
            "final_url": page.url,
            "status": response.status if response else None,
            "title": await page.title(),
            "structured_scripts": scripts,
            "sample_product_links": links,
            "responses": responses,
        }
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(  # noqa: ASYNC240 - one small developer-only report write
                rendered, encoding="utf-8"
            )
        else:
            print(rendered)
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    asyncio.run(inspect(args.url, args.output))


if __name__ == "__main__":
    main()
