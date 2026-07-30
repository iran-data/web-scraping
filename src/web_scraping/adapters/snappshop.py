from web_scraping.adapters.structured import StructuredPageAdapter


class SnappShopAdapter(StructuredPageAdapter):
    shop_name = "snappshop"
    base_url = "https://snappshop.ir"
    product_link_fragment = "/product/"
