"""Inspect Snapp Market search at central Tehran."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Response, async_playwright

LATITUDE = 35.7005
LONGITUDE = 51.3917


async def inspect(output: Path) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            locale="fa-IR",
            geolocation={"latitude": LATITUDE, "longitude": LONGITUDE},
            permissions=["geolocation"],
        )
        page = await context.new_page()
        records: list[dict[str, Any]] = []
        tasks: list[asyncio.Task[None]] = []

        async def capture(response: Response) -> None:
            if "json" not in response.headers.get("content-type", ""):
                return
            record: dict[str, Any] = {
                "url": response.url,
                "status": response.status,
                "method": response.request.method,
                "post_data": response.request.post_data,
            }
            if "snapp.market" in response.url:
                try:
                    record["body"] = await response.json()
                except Exception as error:
                    record["body_error"] = str(error)
            records.append(record)

        page.on("response", lambda response: tasks.append(asyncio.create_task(capture(response))))
        await page.goto("https://snapp.market/")
        await page.wait_for_timeout(3_000)
        search_input = page.locator(
            'input[type="search"]:visible, input[placeholder*="جستجو"]:visible'
        ).first
        if await search_input.count():
            await search_input.fill("شیر")
            await page.wait_for_timeout(1_000)
            await search_input.press("Enter")
        await page.wait_for_timeout(4_000)
        before = await page.locator("body").inner_text()
        candidates = page.get_by_text("شیر", exact=True)
        clicked = await candidates.count() > 0
        if clicked:
            await candidates.last.click()
            await page.wait_for_timeout(5_000)
        sort_button = page.get_by_text("مرتب‌سازی", exact=True).first
        if await sort_button.count():
            await sort_button.click()
            await page.wait_for_timeout(500)
            cheapest = page.get_by_text("ارزانترین", exact=True).last
            if await cheapest.count():
                await cheapest.click()
                await page.wait_for_timeout(3_000)
        product = page.get_by_text("شیر کم چرب تازه مزرعه ماهشام 945 میلی لیتری", exact=True).first
        product_clicked = await product.count() > 0
        if product_clicked:
            await product.click()
            await page.wait_for_timeout(4_000)
        await asyncio.gather(*tasks)
        report = {
            "clicked": clicked,
            "product_clicked": product_clicked,
            "final_url": page.url,
            "body_before_tail": before[-4_000:],
            "body_after_tail": (await page.locator("body").inner_text())[-5_000:],
            "responses": records,
        }
        output.write_text(  # noqa: ASYNC240
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(inspect(args.output))


if __name__ == "__main__":
    main()
