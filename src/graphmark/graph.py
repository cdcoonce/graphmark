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


def _is_intra_note_reference(display: str) -> bool:
    """True for a link that targets no note, e.g. ``[[#Heading]]`` or ``[[#^block]]``.

    Obsidian uses an empty note part to mean "somewhere in this same note". Such a link is
    neither an edge nor a broken link, so it must not be recorded as unresolved — otherwise
    a note that navigates itself heavily looks like the vault's worst offender.
    """
    return not display.split("|")[0].split("#")[0].strip()


def build_catalog(docs: list[Document]) -> dict[str, list[str]]:
    """Map normalized stem → list of rel_paths (len > 1 means ambiguous)."""
    catalog: dict[str, list[str]] = {}
    for doc in docs:
        key = _normalize(Path(doc.rel_path).stem)
        catalog.setdefault(key, []).append(doc.rel_path)
    return catalog


class NormalizeResolver:
    """Resolves wikilink displays via normalized basename, with path-suffix fallback."""

    def __init__(self) -> None:
        # Cache the flattened path list per catalog identity. catalog is invariant for a whole
        # VaultGraph.build(), so folder-style links reuse one flatten instead of rebuilding it
        # on every call. Keyed by id() and single-slot: a new catalog evicts the previous.
        self._flat_cache_id: int | None = None
        self._flat_cache: list[str] | None = None

    @staticmethod
    def _compute_flat(catalog: dict[str, list[str]]) -> list[str]:
        return [p for paths in catalog.values() for p in paths]

    def _flatten_paths(self, catalog: dict[str, list[str]]) -> list[str]:
        if self._flat_cache_id != id(catalog) or self._flat_cache is None:
            self._flat_cache = self._compute_flat(catalog)
            self._flat_cache_id = id(catalog)
        return self._flat_cache

    def resolve(self, display: str, catalog: dict[str, list[str]]) -> str | None:
        # Strip alias: "Note|alias" → "Note"
        display = display.split("|")[0]
        # Strip anchor: "Note#Section" → "Note"
        display = display.split("#")[0]

        if "/" in display:
            # Path-suffix resolution: find unique rel_path ending with "display.md"
            suffix = display.lower() + ".md"
            all_paths = self._flatten_paths(catalog)
            matches = [p for p in all_paths if p.lower().endswith(suffix)]
            return matches[0] if len(matches) == 1 else None

        # Bare-link resolution: normalize and look up in catalog
        key = _normalize(display)
        paths = catalog.get(key)
        if paths is None or len(paths) != 1:
            return None
        return paths[0]


class VaultGraph:
    """Built graph: all nodes plus resolved out/back adjacency.

    ``unresolved`` maps a rel_path to the raw link displays in it that resolved to nothing, in
    extraction order; notes with no such links are absent. It is the inspectable form of what
    build() would otherwise drop silently, and the source of the broken-link health count.
    """

    def __init__(
        self,
        nodes: dict[str, Document],
        out_links: dict[str, set[str]],
        back_links: dict[str, set[str]],
        unresolved: dict[str, list[str]] | None = None,
    ) -> None:
        self.nodes = nodes
        self.out_links = out_links
        self.back_links = back_links
        self.unresolved = unresolved if unresolved is not None else {}

    @classmethod
    def build(
        cls,
        config: VaultConfig,
        extractor: LinkExtractor,
        resolver: Resolver,
    ) -> VaultGraph:
        root = config.root
        # rglob on a missing path silently yields nothing, so an unvalidated root turns a typo
        # into a structurally valid empty graph. An existing-but-empty vault is still legitimate.
        if not root.is_dir():
            raise ValueError(f"vault root does not exist or is not a directory: {root}")
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

        unresolved: dict[str, list[str]] = {}

        for doc in docs:
            for display in extractor.extract(doc.text):
                if _is_intra_note_reference(display):
                    continue
                target = resolver.resolve(display, catalog)
                if target is None:
                    # Unresolvable OR ambiguous — the Resolver protocol conflates the two, and
                    # both are equally broken from a vault-health view. Record the raw display
                    # (what a human has to go fix) once per occurrence.
                    unresolved.setdefault(doc.rel_path, []).append(display)
                elif target != doc.rel_path:
                    out_links[doc.rel_path].add(target)

        for src, targets in out_links.items():
            for dst in targets:
                back_links[dst].add(src)

        return cls(nodes, out_links, back_links, unresolved)
