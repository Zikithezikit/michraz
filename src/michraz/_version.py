"""Package version, read from the installed distribution metadata."""

from importlib.metadata import PackageNotFoundError, version

DISTRIBUTION_NAME = "michraz"

try:
    __version__ = version(DISTRIBUTION_NAME)
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0+unknown"
