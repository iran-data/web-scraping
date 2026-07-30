from decimal import Decimal

from web_scraping.normalization import (
    absolute_url,
    normalize_digits,
    normalize_price,
    normalize_rating,
    normalize_text,
)


def test_persian_and_arabic_normalization() -> None:
    assert normalize_digits("۱۲٣۴") == "1234"
    assert normalize_text("  كالا\u200cي  خوب ") == "کالای خوب"


def test_price_normalization() -> None:
    assert normalize_price("۱٬۲۳۴ تومان", source_currency="IRT") == Decimal("1234")  # noqa: RUF001
    assert normalize_price("۱۲۳۴ ریال") == Decimal("123.4")


def test_rating_and_urls() -> None:
    assert normalize_rating(80, source_max=100) == 4
    assert absolute_url("https://example.test", "/p/1") == "https://example.test/p/1"
