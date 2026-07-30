"""Package exceptions."""


class ScraperError(Exception):
    """Base package error."""


class NavigationError(ScraperError):
    """A page could not be loaded after retries."""


class ParsingError(ScraperError):
    """Expected structured content was missing or incompatible."""


class LayoutChangedError(ParsingError):
    """A site's known page contract no longer matches."""


class ProductNotFoundError(ScraperError):
    """The requested product does not exist."""


class UnsupportedFeatureError(ScraperError):
    """The adapter/site does not support the requested feature."""


class UpstreamUnavailableError(ScraperError):
    """A source's required first-party or linked provider service is unavailable."""


class BotChallengeError(ScraperError):
    """A CAPTCHA or bot challenge requires human intervention."""
