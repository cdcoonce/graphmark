"""graphmark — deterministic knowledge-graph analysis for markdown/wikilink vaults."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("graphmark")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0+unknown"
