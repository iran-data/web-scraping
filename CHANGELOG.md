# Changelog

All notable changes to this project are documented in this file. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and releases use
[Semantic Versioning](https://semver.org/).

## [0.1.0] - 2026-08-10

### Added

- Async, adapter-based Playwright architecture with typed normalized models.
- Commerce sources for Digikala, Technolife, Snapp Market, Digikala Jet, Torob, Bama, and
  Hamrah Mechanic.
- Transportation sources for Safarmarket flights/trains and Safar724 buses.
- Bama market, factory, and agency reference-price support.
- Persian text/digit, URL, rating, availability, and rial-to-toman normalization.
- Configurable retries, timeouts, concurrency, rate limiting, user agent, visible mode, and
  reusable browser sessions.
- Structured logging and explicit navigation, parsing, layout, challenge, unsupported-feature,
  and upstream-availability exceptions.
- Product, price, and transportation CLI commands.
- Sanitized parser fixtures, mocked browser tests, low-volume live contracts, and weekly GitHub
  Actions monitoring.
- Production documentation, contributor guidance, and security policy.

### Changed

- Safarmarket response capture waits for the expected structured contract and treats a verified
  no-train response as an empty result.
- Safar724 live monitoring uses a near-term inventory window.

### Removed

- Snapp Shop support and all associated source, inspection, registry, test, and documentation
  artifacts.
