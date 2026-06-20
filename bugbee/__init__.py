"""Top level package for BugBee.

Provides version information and exposes the public API.
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover – during development the package may not be installed yet
    __version__ = "0.1.0"

__all__ = ["__version__"]
