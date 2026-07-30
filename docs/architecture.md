# Architecture

The package is organized around web sources, not shops.

## Core layer

`BaseSource` provides configuration, Playwright session ownership, and async context-manager
behavior. It intentionally has no abstract content methods because different domains expose
different records and operations.

The registry stores `BaseSource` classes and supports optional filtering by `SourceCategory`.
The currently defined categories are `commerce`, `transportation`, and `other`. More specific
categories should be added only when the project has a concrete source that requires one.

## Domain layer

`CommerceAdapter` is the current commerce contract. It defines product search, detail lookup,
pagination iteration, and optional popularity/best-selling helpers. `BaseShopAdapter` remains an
alias for compatibility but should not be used as the foundation for unrelated domains.

`TransportationSource` defines flight, train, and bus searches over `TicketSearchQuery`,
`TicketOffer`, and `TicketSearchResult`. Route identifiers deliberately remain source-native
because airport codes, station IDs, and bus city IDs belong to different namespaces.

Normalized commerce records remain in `Product`, `SearchPage`, `CarPrice`, and `CarPricePage`.
Future domains should define separate models rather than adding unrelated optional fields to
`Product`.

## Site layer

Each website has one concrete source class. A concrete class may add capabilities beyond its
domain interface; for example, Bama adds `REFERENCE_PRICES`.

Capabilities describe verified behavior, not desired behavior. A source should not advertise a
capability when the site ignores the associated parameter or the implementation only guesses it.

## Compatibility

The following commerce names remain supported:

- `BaseShopAdapter` → `CommerceAdapter`
- `create_adapter()` creates commerce sources only
- `supported_shops()` returns commerce sources only

New domain-neutral integrations should use `BaseSource`, `create_source()`, and
`supported_sources()`.
