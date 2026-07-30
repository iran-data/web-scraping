"""Inspect Technolife by performing a search through its visible controls."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from playwright.async_api import Response, async_playwright


async def inspect(keyword: str, output: Path) -> None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(locale="fa-IR")
        responses: list[dict[str, Any]] = []
        response_tasks: list[asyncio.Task[None]] = []

        async def capture(response: Response) -> None:
            content_type = response.headers.get("content-type", "")
            if "json" not in content_type:
                return
            record: dict[str, Any] = {
                "url": response.url,
                "status": response.status,
                "content_type": content_type,
                "request_method": response.request.method,
                "request_post_data": response.request.post_data,
            }
            if "technolife.com" in response.url:
                try:
                    record["body"] = await response.json()
                except Exception as error:
                    record["body_error"] = str(error)
            responses.append(record)

        def schedule_capture(response: Response) -> None:
            response_tasks.append(asyncio.create_task(capture(response)))

        page.on("response", schedule_capture)
        await page.goto("https://www.technolife.com/", wait_until="domcontentloaded")
        await page.wait_for_timeout(2_000)
        inputs = page.locator("input")
        input_report = await inputs.evaluate_all(
            """nodes => nodes.map((node, index) => ({
                index,
                type: node.type,
                placeholder: node.placeholder,
                ariaLabel: node.getAttribute('aria-label'),
                name: node.name,
                visible: Boolean(node.offsetWidth || node.offsetHeight),
            }))"""
        )
        search_input = page.locator(
            'input[placeholder*="محصول"]:visible, '
            'input[placeholder*="جستجو"]:visible, input[type="search"]:visible'
        )
        if await search_input.count() == 0:
            raise RuntimeError(f"No visible search input. Inputs: {input_report}")
        await search_input.first.fill(keyword)
        await page.wait_for_timeout(1_500)
        suggestions = await page.locator("body").inner_text()
        await search_input.first.press("Enter")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(5_000)
        links = await page.locator('a[href*="/product-"]').evaluate_all(
            """nodes => [...new Map(nodes.map(node => [node.href, {
                href: node.href,
                text: node.innerText,
                parentText: node.parentElement?.innerText || '',
            }])).values()].slice(0, 10)"""
        )
        sort_controls = await page.get_by_text("کمترین قیمت", exact=True).evaluate_all(
            """nodes => nodes.map(node => ({
                tag: node.tagName,
                html: node.outerHTML,
                parent: node.parentElement?.outerHTML.slice(0, 1000),
            }))"""
        )
        sort_urls: dict[str, str] = {}
        for label in ("کمترین قیمت", "بیشترین قیمت", "جدیدترین", "پرفروش ترین"):
            button = page.get_by_role("button", name=label, exact=True).first
            await button.click()
            await page.wait_for_timeout(1_000)
            sort_urls[label] = page.url
        next_data_text = await page.locator("script#__NEXT_DATA__").text_content()
        await asyncio.gather(*response_tasks)
        report = {
            "keyword": keyword,
            "final_url": page.url,
            "title": await page.title(),
            "inputs": input_report,
            "suggestions_tail": suggestions[-2_000:],
            "product_links": links,
            "sort_controls": sort_controls,
            "sort_urls": sort_urls,
            "next_data": json.loads(next_data_text) if next_data_text else None,
            "body_tail": (await page.locator("body").inner_text())[-5_000:],
            "responses": responses,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(  # noqa: ASYNC240 - one developer inspection report
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("keyword")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(inspect(args.keyword, args.output))


if __name__ == "__main__":
    main()
