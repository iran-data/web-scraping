from web_scraping import (
    BaseSource,
    CommerceAdapter,
    SourceCapability,
    SourceCategory,
    create_adapter,
    create_source,
    supported_shops,
    supported_sources,
)


def test_generic_source_registry_exposes_categories() -> None:
    assert tuple(SourceCategory) == (
        SourceCategory.COMMERCE,
        SourceCategory.TRANSPORTATION,
        SourceCategory.OTHER,
    )
    assert set(supported_sources()) == {*supported_shops(), "safar724", "safarmarket"}
    assert supported_sources(SourceCategory.COMMERCE) == supported_shops()
    source = create_source("digikala")
    assert isinstance(source, BaseSource)
    assert source.category == SourceCategory.COMMERCE
    assert source.source_name == "digikala"


def test_legacy_commerce_factory_remains_supported() -> None:
    adapter = create_adapter("bama")
    assert isinstance(adapter, CommerceAdapter)
    assert SourceCapability.REFERENCE_PRICES in adapter.capabilities
