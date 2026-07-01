"""Graph construction: catalog building, link resolution, and VaultGraph."""

from __future__ import annotations

import string
from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.interfaces import LinkExtractor, Resolver
from graphmark.model import Document
from graphmark.parse import parse_document

_PUNCT_TABLE = str.maketrans(string.punctuation, " " * len(string.punctuation))


def _normalize(text: str) -> str:
    """Lowercase, replace punctuation with spaces, collapse whitespace."""
    return " ".join(text.lower().translate(_PUNCT_TABLE).split())


def build_catalog(docs: list[Document]) -> dict[str, list[str]]:
    """Map normalized stem → list of rel_paths (len > 1 means ambiguous)."""
    catalog: dict[str, list[str]] = {}
    for doc in docs:
        key = _normalize(Path(doc.rel_path).stem)
        catalog.setdefault(key, []).append(doc.rel_path)
    return catalog


class NormalizeResolver:
    """Resolves wikilink displays via normalized basename, with path-suffix fallback."""

    def resolve(self, display: str, catalog: dict[str, list[str]]) -> str | None:
        # Strip alias: "Note|alias" → "Note"
        display = display.split("|")[0]
        # Strip anchor: "Note#Section" → "Note"
        display = display.split("#")[0]

        if "/" in display:
            # Path-suffix resolution: find unique rel_path ending with "display.md"
            suffix = display.lower() + ".md"
            all_paths = [p for paths in catalog.values() for p in paths]
            matches = [p for p in all_paths if p.lower().endswith(suffix)]
            return matches[0] if len(matches) == 1 else None

        # Bare-link resolution: normalize and look up in catalog
        key = _normalize(display)
        paths = catalog.get(key)
        if paths is None or len(paths) != 1:
            return None
        return paths[0]


class VaultGraph:
    """Built graph: all nodes plus resolved out/back adjacency."""

    def __init__(
        self,
        nodes: dict[str, Document],
        out_links: dict[str, set[str]],
        back_links: dict[str, set[str]],
    ) -> None:
        self.nodes = nodes
        self.out_links = out_links
        self.back_links = back_links

    @classmethod
    def build(
        cls,
        config: VaultConfig,
        extractor: LinkExtractor,
        resolver: Resolver,
    ) -> VaultGraph:
        root = config.root
        excluded = set(config.excluded_dirs)
        rules = set(config.rules_files)

        scoped = set(config.scoped_folders)
        md_files: list[Path] = []
        for path in sorted(root.rglob("*.md")):
            rel_parts = path.relative_to(root).parts
            if scoped and rel_parts[0] not in scoped:
                continue
            if any(p in excluded for p in rel_parts[:-1]):
                continue
            if path.name in rules:
                continue
            md_files.append(path)

        docs = [parse_document(p, root) for p in md_files]
        nodes = {doc.rel_path: doc for doc in docs}
        catalog = build_catalog(docs)

        out_links: dict[str, set[str]] = {rel: set() for rel in nodes}
        back_links: dict[str, set[str]] = {rel: set() for rel in nodes}

        for doc in docs:
            for display in extractor.extract(doc.text):
                target = resolver.resolve(display, catalog)
                if target is not None and target != doc.rel_path:
                    out_links[doc.rel_path].add(target)

        for src, targets in out_links.items():
            for dst in targets:
                back_links[dst].add(src)

        return cls(nodes, out_links, back_links)
