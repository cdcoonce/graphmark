"""graphmark — deterministic knowledge-graph analysis for markdown/wikilink vaults.

Quickstart::

    import graphmark

    graph = graphmark.build("/path/to/vault")
    print(graphmark.stats(graph))

``build`` is a convenience over ``VaultGraph.build``: it defaults the extractor/resolver pair and
accepts a plain path. Everything it composes is re-exported here too, so a caller who needs a
custom link syntax or a config file never has to reach into submodules.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from graphmark.check import run_check, unresolved_link_count
from graphmark.config import CheckPolicy, VaultConfig, load_config
from graphmark.dismiss import (
    active_dismissed_sigs,
    load_dismissed,
    record_dismissal,
    weaklink_sig,
)
from graphmark.export import to_dot, to_json
from graphmark.graph import (
    DIAGNOSIS_REASONS,
    SUGGEST_MAX_MATCHES,
    SUGGEST_MIN_COVERAGE,
    LinkDiagnosis,
    NormalizeResolver,
    VaultGraph,
    build_catalog,
    candidates_for,
    diagnose,
    suggest_notes,
)
from graphmark.interfaces import LinkExtractor, Resolver, Similarity
from graphmark.metrics import (
    GAPS_DEFAULT_BAND,
    GAPS_DEFAULT_HUB_DEGREE,
    GAPS_DEFAULT_K,
    GAPS_DEFAULT_MAX_SCORE,
    GAPS_DEFAULT_THRESHOLD,
    bridges,
    clusters,
    gaps,
    hubs,
    neighborhood,
    orphans,
    pagerank,
    siloed_notes,
    stats,
)
from graphmark.model import Document
from graphmark.parse import WikilinkExtractor, parse_document

try:
    __version__ = version("graphmark")
except PackageNotFoundError:  # un-installed source checkout
    __version__ = "0.0.0+unknown"


def build(
    source: str | Path | VaultConfig,
    *,
    extractor: LinkExtractor | None = None,
    resolver: Resolver | None = None,
) -> VaultGraph:
    """Build a VaultGraph from a vault root or a VaultConfig.

    ``source`` is either a path to the vault root (``str`` or ``Path``, using default policy) or
    a fully configured ``VaultConfig``. To drive it from a TOML file, pair it with
    ``load_config``::

        graph = graphmark.build(graphmark.load_config("vault.toml"))

    ``extractor`` and ``resolver`` default to the wikilink/normalize pair, which is the only
    combination shipped today; pass your own to support an alternate link syntax.
    """
    config = source if isinstance(source, VaultConfig) else VaultConfig(root=Path(source))
    return VaultGraph.build(
        config,
        extractor if extractor is not None else WikilinkExtractor(),
        resolver if resolver is not None else NormalizeResolver(),
    )


__all__ = [
    "GAPS_DEFAULT_BAND",
    "GAPS_DEFAULT_HUB_DEGREE",
    "GAPS_DEFAULT_K",
    "GAPS_DEFAULT_MAX_SCORE",
    "GAPS_DEFAULT_THRESHOLD",
    "CheckPolicy",
    "Document",
    "LinkExtractor",
    "DIAGNOSIS_REASONS",
    "SUGGEST_MAX_MATCHES",
    "SUGGEST_MIN_COVERAGE",
    "LinkDiagnosis",
    "NormalizeResolver",
    "Resolver",
    "Similarity",
    "VaultConfig",
    "VaultGraph",
    "WikilinkExtractor",
    "__version__",
    "active_dismissed_sigs",
    "bridges",
    "build",
    "build_catalog",
    "candidates_for",
    "diagnose",
    "suggest_notes",
    "clusters",
    "gaps",
    "hubs",
    "load_config",
    "load_dismissed",
    "neighborhood",
    "orphans",
    "pagerank",
    "parse_document",
    "record_dismissal",
    "run_check",
    "siloed_notes",
    "stats",
    "to_dot",
    "to_json",
    "unresolved_link_count",
    "weaklink_sig",
]
