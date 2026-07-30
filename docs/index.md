# Documentation

This documentation describes the public contracts, deployment concerns, and maintenance
workflow for `web-scraping`.

## For users

- [Getting started](getting-started.md): installation, browser setup, first search, and common
  errors.
- [Python API](api.md): factories, domain interfaces, models, configuration, and exceptions.
- [CLI reference](cli.md): every command and option with examples.
- [Source support](sites.md): inspected website contracts, supported behavior, and known
  limitations.

## For operators

- [Operations](operations.md): rate limits, sessions, challenges, logging, observability,
  deployment, and incident response.
- [Testing and CI](testing.md): offline tests, live contracts, weekly automation, fixtures, and
  interpreting failures.

## For contributors

- [Architecture](architecture.md): source, domain, and site layers.
- [Adding a source](adding-a-source.md): inspection-to-release checklist and parser standards.

The README is the project entry point. These pages are the detailed reference. When behavior and
documentation disagree, treat the tested Python API as authoritative and file an issue so the
documentation can be corrected.
