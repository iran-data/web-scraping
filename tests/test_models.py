from dataclasses import FrozenInstanceError

import pytest

from web_scraping.models import Availability, Product, SearchPage


def test_models_are_immutable_and_typed() -> None:
    product = Product(
        shop="shop",
        identifier="1",
        title="title",
        url="https://example.test/1",
        availability=Availability.UNKNOWN,
    )
    page = SearchPage((product,), page=1, has_next=False)
    assert page.items == (product,)
    with pytest.raises(FrozenInstanceError):
        product.title = "changed"  # type: ignore[misc]
