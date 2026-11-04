"""Exceptions raised by michraz."""


class MichrazError(Exception):
    """Base class for every error raised by michraz."""


class _SourceError(MichrazError):
    """Base class for errors tied to one data source."""

    def __init__(self, source: str, message: str) -> None:
        super().__init__(f"{source}: {message}")
        self.source = source
        self.message = message


class SourceUnavailableError(_SourceError):
    """A source could not be reached or answered with an error status.

    Attributes:
        source: Name of the source, for example ``"rmi"``.
        message: What went wrong, without the source prefix.
    """


class SourceFormatError(_SourceError):
    """A source answered, but the response is not in the expected shape.

    The message includes a truncated sample of the response to make bug reports useful.

    Attributes:
        source: Name of the source, for example ``"rmi"``.
        message: What went wrong, without the source prefix.
    """
