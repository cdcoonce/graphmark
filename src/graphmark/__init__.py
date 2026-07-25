"""graphmark — deterministic knowledge-graph analysis for markdown/wikilink vaults."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("graphmark")
except PackageNotFoundError:  # un-installed source checkout
    __version__ = "0.0.0+unknown"
