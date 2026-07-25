"""Graph construction: catalog building, link resolution, and VaultGraph."""

from __future__ import annotations

import re
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


# A trailing dot plus a short alphanumeric run — a plausible file extension. Deliberately
# strict so a note title like "v1.2 release notes" (spaces after the dot) is not mistaken
# for one.
_FILE_SUFFIX_RE = re.compile(r"\.[A-Za-z0-9]{1,10}$")


def _strip_display(display: str) -> str:
    """Reduce a raw wikilink display to its note part: no alias, no anchor, no ``.md``.

    Obsidian treats ``[[Note]]``, ``[[Note|alias]]``, ``[[Note#Section]]`` and ``[[Note.md]]`` as
    the same link, so every place that asks "which note does this display name?" must strip the
    same three things. Shared by the resolver and the out-of-scope check so they cannot drift.
    """
    target = display.split("|")[0].split("#")[0].strip()
    if target.lower().endswith(".md"):
        target = target[: -len(".md")]
    return target


def _targets_non_note_file(display: str) -> bool:
    """True for a link to a file graphmark does not index, e.g. ``[[Board.canvas]]``.

    Obsidian wikilinks legitimately target Bases, Canvas, images and PDFs. graphmark only
    indexes markdown, so it has no basis to call such a link broken — reporting it as
    unresolved just fills the vault-health count with entries nobody can act on.

    Only ever consulted after the resolver has already failed, so a note that genuinely
    resolves (say a real ``report.v2.md`` linked as ``[[report.v2]]``) is never suppressed.
    """
    target = display.split("|")[0].split("#")[0].strip()
    match = _FILE_SUFFIX_RE.search(target)
    return bool(match) and match.group(0).lower() != ".md"


def _targets_out_of_scope_note(display: str, out_of_scope: dict[str, list[str]]) -> bool:
    """True for a link to a markdown note that exists but is outside the configured scope.

    ``build`` drops unscoped folders, excluded dirs and rules files from the catalog, so links to
    them fail the resolver — yet the link is correct, Obsidian follows it, and there is nothing for
    anyone to fix. Reporting it as broken just fills the vault-health count with noise.

    Only ever consulted after the resolver has already failed, so an in-graph note always wins over
    an out-of-scope namesake. **Any** candidate suppresses: out-of-scope notes are never link
    targets, so ambiguity among them says nothing about whether the in-graph link is broken.
    """
    target = _strip_display(display)
    if not target:
        return False
    if "/" in target:
        suffix = target.lower() + ".md"
        return any(
            path.lower().endswith(suffix) for paths in out_of_scope.values() for path in paths
        )
    return _normalize(target) in out_of_scope


def _is_intra_note_reference(display: str) -> bool:
    """True for a link that targets no note, e.g. ``[[#Heading]]`` or ``[[#^block]]``.

    Obsidian uses an empty note part to mean "somewhere in this same note". Such a link is
    neither an edge nor a broken link, so it must not be recorded as unresolved — otherwise
    a note that navigates itself heavily looks like the vault's worst offender.
    """
    return not display.split("|")[0].split("#")[0].strip()


def build_catalog(docs: list[Document]) -> dict[str, list[str]]:
    """Map normalized stem → list of rel_paths (len > 1 means ambiguous).

    Value lists are sorted by rel_path. ``build`` already walks in path order, but ``Path``
    ordering and rel_path string ordering disagree where a separator meets punctuation
    (``a-b/x.md`` vs ``a/b.md``), and this mapping is public state feeding byte-stable reports —
    so the order is established here rather than inherited.
    """
    catalog: dict[str, list[str]] = {}
    for doc in docs:
        key = _normalize(Path(doc.rel_path).stem)
        catalog.setdefault(key, []).append(doc.rel_path)
    for paths in catalog.values():
        paths.sort()
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
        # Alias ("Note|alias"), anchor ("Note#Section") and an explicit ".md" extension all name
        # the same note. Stripped before both branches below: the path-suffix branch appends
        # ".md" itself, and the bare branch would otherwise normalize to the key "note md".
        display = _strip_display(display)

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

    ``catalog`` and ``out_of_scope`` are the resolution state build() consulted, retained instead of
    discarded: normalized stem → rel_paths, in path order, for in-scope notes and for markdown that
    exists outside the configured scope respectively. A ``catalog`` key with two or more paths *is*
    an ambiguity set. Consumers need both to say anything about a link beyond whether it resolved —
    without them, the only way to explain a broken link is to rebuild the whole parse/catalog/
    resolve stack, and a second stack drifts from this one.
    """

    def __init__(
        self,
        nodes: dict[str, Document],
        out_links: dict[str, set[str]],
        back_links: dict[str, set[str]],
        unresolved: dict[str, list[str]] | None = None,
        catalog: dict[str, list[str]] | None = None,
        out_of_scope: dict[str, list[str]] | None = None,
    ) -> None:
        self.nodes = nodes
        self.out_links = out_links
        self.back_links = back_links
        self.unresolved = unresolved if unresolved is not None else {}
        self.catalog = catalog if catalog is not None else {}
        self.out_of_scope = out_of_scope if out_of_scope is not None else {}

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
        # Markdown that exists but is out of scope, normalized stem → rel_paths. Collected in
        # this same walk (no extra I/O) so a link to one can be told apart from a link to a note
        # that exists nowhere at all.
        out_of_scope: dict[str, list[str]] = {}
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(root)
            rel_parts = rel.parts
            if (
                (scoped and rel_parts[0] not in scoped)
                or any(p in excluded for p in rel_parts[:-1])
                or path.name in rules
            ):
                out_of_scope.setdefault(_normalize(path.stem), []).append(rel.as_posix())
                continue
            md_files.append(path)

        for paths in out_of_scope.values():
            paths.sort()  # same rel_path ordering guarantee as build_catalog

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
                    if _targets_non_note_file(display) or _targets_out_of_scope_note(
                        display, out_of_scope
                    ):
                        continue  # out of scope, not a broken note link
                    # Unresolvable OR ambiguous — the Resolver protocol conflates the two, and
                    # both are equally broken from a vault-health view. Record the raw display
                    # (what a human has to go fix) once per occurrence.
                    unresolved.setdefault(doc.rel_path, []).append(display)
                elif target != doc.rel_path:
                    out_links[doc.rel_path].add(target)

        for src, targets in out_links.items():
            for dst in targets:
                back_links[dst].add(src)

        return cls(nodes, out_links, back_links, unresolved, catalog, out_of_scope)
