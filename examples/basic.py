"""Search Digikala and then load the first result's detail page."""

import asyncio

from web_scraping import ScraperConfig, create_adapter


async def main() -> None:
    config = ScraperConfig(headless=True, requests_per_second=0.5)
    async with create_adapter("digikala", config) as shop:
        page = await shop.search("هدفون", page=1)
        if page.items:
            product = await shop.get_product(page.items[0].identifier)
            print(product)


if __name__ == "__main__":
    asyncio.run(main())
