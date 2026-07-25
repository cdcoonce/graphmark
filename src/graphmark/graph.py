"""Graph construction: catalog building, link resolution, diagnosis, and VaultGraph."""

from __future__ import annotations

import re
import string
from dataclasses import dataclass, field, replace
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


def candidates_for(display: str, catalog: dict[str, list[str]]) -> list[str]:
    """Every rel_path in ``catalog`` that ``display`` names, sorted; empty if it names none.

    Answers "what did this display match?" — the question behind both an ambiguity verdict (the
    resolver saw these and refused to pick) and the out-of-scope check (a link into unindexed
    markdown). Deciding *uniqueness* remains the ``Resolver``'s job; this only reports matches, so
    the two never disagree about which notes were in play.

    Matching mirrors ``NormalizeResolver``: bare displays by normalized stem, ``[[folder/note]]``
    by path suffix. Both branches read the same stripped display.
    """
    target = _strip_display(display)
    if not target:
        return []
    if "/" in target:
        suffix = target.lower() + ".md"
        return sorted(
            path for paths in catalog.values() for path in paths if path.lower().endswith(suffix)
        )
    return list(catalog.get(_normalize(target), ()))


def build_aliases(docs: list[Document], catalog: dict[str, list[str]]) -> dict[str, str]:
    """Map normalized alias → rel_path, for aliases that unambiguously name one note.

    Obsidian's ``aliases:`` property declares additional real names for a note, so a link written
    against one is not a broken link. Two rules keep this conservative, and both matter:

    * **An alias that collides with any real note name is dropped entirely** — not merely
      outranked. A note's own title must never be hijackable by someone else's alias, and an
      already-ambiguous basename must not be rescued into resolving by a third note's alias.
    * **An alias claimed by two or more notes resolves to nothing** — the same refusal graphmark
      already applies to colliding basenames. Ambiguity stays ambiguous.

    Alias keys go through ``_normalize``, the function that builds catalog keys, so an alias and a
    note name can never drift apart on case or punctuation.
    """
    claims: dict[str, set[str]] = {}
    for doc in docs:
        raw = doc.frontmatter.get("aliases")
        # A scalar is one alias; a list is many; anything else (a number, a mapping, a missing
        # key) yields none rather than raising — a note someone is mid-edit must not break a build.
        if isinstance(raw, str):
            values = [raw]
        elif isinstance(raw, list):
            values = [v for v in raw if isinstance(v, str)]
        else:
            continue
        for alias in values:
            # A path is not a name: "[[folder/note]]" is resolved by path suffix, never by alias.
            if "/" in alias:
                continue
            key = _normalize(alias)
            if not key or key in catalog:
                continue
            claims.setdefault(key, set()).add(doc.rel_path)
    return {key: paths.pop() for key, paths in claims.items() if len(paths) == 1}


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


#: A display matching more than this many notes names a *topic*, not a mistyped note, and gets no
#: suggestions at all. Calibrated, not chosen: on the reference vault ``[[AMRT]]`` matched 47 notes
#: while ``[[Priya Raghavan]]`` needs a cap of at least 12 to survive (that token appears in 9 note
#: stems), so 12 is the lowest value that keeps every human-confirmed useful suggestion.
SUGGEST_MAX_MATCHES = 12

#: When a candidate's name sits *inside* a longer display, the fraction of the display it must
#: account for. ``[[fable-prompt-technique-reference]]`` → ``fable-prompt-technique`` covers 3 of 4
#: tokens and is the answer; ``[[Dagster PJM InSchedules]]`` → ``Dagster`` covers 1 of 3 and is a
#: real note that is not the target — the shape that made the old suggestions untrustworthy. 0.4 is
#: the highest floor that keeps every useful suggestion in the annotated baseline.
SUGGEST_MIN_COVERAGE = 0.4

#: Note stems that name nothing — the note's identity lives in its parent folder instead. Kept
#: deliberately short: ``index`` is NOT here, because a vault's ``personal/Index.md`` is a real,
#: linkable note and re-keying it onto its folder would lose the actual answer.
GENERIC_STEMS = frozenset({"skill", "readme"})


def _content_tokens(text: str) -> frozenset[str]:
    """Normalized tokens with pure-digit runs dropped.

    Date prefixes are filing metadata, not content: ``2026-04-11-mood-tracker`` and
    ``Mood Tracker`` are the same note to a human, and the dated twin is the single most common
    near-miss shape in a journal-style vault.
    """
    return frozenset(t for t in _normalize(text).split() if not t.isdigit())


def _suggestion_keys(catalog: dict[str, list[str]]) -> list[tuple[str, frozenset[str]]]:
    """(rel_path, name tokens) for every note, keyed by folder where the stem is generic."""
    keys: list[tuple[str, frozenset[str]]] = []
    for paths in catalog.values():
        for rel in paths:
            path = Path(rel)
            name = path.parent.name if path.stem.lower() in GENERIC_STEMS else path.stem
            tokens = _content_tokens(name)
            if tokens:
                keys.append((rel, tokens))
    return keys


def suggest_notes(display: str, catalog: dict[str, list[str]], k: int) -> tuple[str, ...]:
    """Up to ``k`` notes whose names are near-misses for ``display``, best first.

    Matching is **directional**, which is what separates a suggestion from noise:

    * the display's tokens inside a candidate's — the display abbreviates a longer title
      (``[[Jordan]]`` → ``Jordan Ellis``). Always offered; a short display naturally names a
      longer note.
    * a candidate's tokens inside the display's — offered only when the candidate accounts for at
      least ``SUGGEST_MIN_COVERAGE`` of the display. Dropping a suffix is a real answer; matching
      one word out of five is a wrong answer that invites a wrong repair.
    * neither — rejected. Partial overlap produced no useful suggestion anywhere in the annotated
      baseline, and rejecting it is what holds the false-suggestion rate at zero.

    Ranked by how much of the longer name the match accounts for, ties broken by rel_path so the
    output is byte-stable.
    """
    display_tokens = _content_tokens(display)
    if not display_tokens or k <= 0:
        return ()

    scored: list[tuple[float, str]] = []
    for rel, name_tokens in _suggestion_keys(catalog):
        if display_tokens <= name_tokens:
            score = len(display_tokens) / len(name_tokens)
        elif name_tokens <= display_tokens:
            score = len(name_tokens) / len(display_tokens)
            if score < SUGGEST_MIN_COVERAGE:
                continue
        else:
            continue
        scored.append((score, rel))

    # A display that matches half the vault is a topic. Offering its "best" dozen would be
    # confident nonsense, so it gets nothing.
    if len(scored) > SUGGEST_MAX_MATCHES:
        return ()

    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return tuple(rel for _, rel in scored[:k])


#: Every value ``LinkDiagnosis.reason`` can take, in the order they are decided. A consumer
#: switches on these strings, so the set is part of the public contract.
DIAGNOSIS_REASONS = (
    "resolved",
    "ambiguous",
    "non-note-file",
    "out-of-scope-note",
    "missing",
    "intra-note",
)


@dataclass(frozen=True)
class LinkDiagnosis:
    """Why a single wikilink display ended up where it did.

    ``build`` sorts every link into one of the ``DIAGNOSIS_REASONS`` and then keeps only whether it
    resolved, which conflates an *ambiguous* link with a *missing* one. Those need opposite repairs
    — disambiguate against the colliding notes, versus create or delete the target — so a consumer
    holding only ``unresolved`` cannot act without rebuilding the resolver itself.

    ``target`` is the resolved rel_path, set only when ``reason == "resolved"``; the caller recovers
    the note's canonical title from its stem, which is what makes a case repair like
    ``[[jordan ellis]]`` → ``[[Jordan Ellis]]`` possible.

    ``candidates`` carries the rel_paths in play: the colliding notes for ``ambiguous``, the
    unindexed markdown for ``out-of-scope-note``, and — only when ``diagnose`` is asked for them —
    the near-miss suggestions for ``missing``. Empty for every other reason.

    ``via`` distinguishes the two ways a link can resolve. That distinction is not cosmetic: an
    alias resolution looked identical to a stem resolution, and a vault reporting many broken links
    beside zero alias resolutions is the exact signature of the defect that hid for six releases.
    """

    display: str
    target: str | None = None
    reason: str = "missing"
    candidates: tuple[str, ...] = field(default=())
    #: How a ``resolved`` verdict was reached — ``"stem"`` (catalog name or path suffix) or
    #: ``"alias"`` (frontmatter ``aliases:``). ``None`` for every other reason. Recorded here
    #: rather than re-derived by callers, so a counter can never disagree with the classifier.
    via: str | None = None


def _diagnose(
    display: str,
    catalog: dict[str, list[str]],
    out_of_scope: dict[str, list[str]],
    resolver: Resolver,
    aliases: dict[str, str] | None = None,
) -> LinkDiagnosis:
    """Classify one display against already-built resolution state.

    The single classifier: ``build`` calls this while assembling a graph (before a ``VaultGraph``
    exists to pass), and the public ``diagnose`` wraps it for callers holding a built graph. Two
    independent classifiers would drift from each other inside the package, which is the exact
    failure this surface exists to remove.
    """
    if _is_intra_note_reference(display):
        return LinkDiagnosis(display=display, reason="intra-note")

    target = resolver.resolve(display, catalog)
    if target is not None:
        return LinkDiagnosis(display=display, target=target, reason="resolved", via="stem")

    # The resolver runs first, so a real note named X always beats an alias X — otherwise renaming
    # a note could silently hijack live links. An alias hit is a genuine resolution, not a
    # consolation: it names the note as surely as the filename does.
    #
    # Given the rules build_aliases already enforces, this ordering is defense in depth rather
    # than load-bearing: an alias key can never collide with a catalog key (dropped at index
    # time), and a path-qualified display is excluded from alias lookup below, so no display can
    # match both paths. Mutating the order leaves the suite green, which is expected — the
    # ordering is insurance against a future relaxation of those rules, not the mechanism.
    if aliases:
        stripped = _strip_display(display)
        if stripped and "/" not in stripped:
            aliased = aliases.get(_normalize(stripped))
            if aliased is not None:
                return LinkDiagnosis(
                    display=display, target=aliased, reason="resolved", via="alias"
                )

    # The resolver declined. Whether it declined because nothing matched or because too much did
    # is the distinction consumers need, and only the catalog can answer it.
    collisions = candidates_for(display, catalog)
    if collisions:
        return LinkDiagnosis(display=display, reason="ambiguous", candidates=tuple(collisions))

    # Ordered as build has always ordered it: a "[[Board.canvas]]" is a non-note file even if some
    # out-of-scope note happens to share the stem.
    if _targets_non_note_file(display):
        return LinkDiagnosis(display=display, reason="non-note-file")

    unindexed = candidates_for(display, out_of_scope)
    if unindexed:
        return LinkDiagnosis(
            display=display, reason="out-of-scope-note", candidates=tuple(unindexed)
        )

    return LinkDiagnosis(display=display, reason="missing")


def diagnose(graph: VaultGraph, display: str, *, suggest: int = 0) -> LinkDiagnosis:
    """Explain what ``display`` names in ``graph`` — see :class:`LinkDiagnosis`.

    Uses the resolver the graph was built with, so a diagnosis can never contradict the graph it
    describes. A directly constructed ``VaultGraph`` with no resolver falls back to
    ``NormalizeResolver``.

    ``suggest=k`` fills ``candidates`` with up to k near-miss notes — but only for a ``missing``
    verdict, since every other reason either already carries the rel_paths in play or has nothing
    to look for. The default of 0 does no extra work at all, keeping the vault-health gate's hot
    path free of it.
    """
    if suggest < 0:
        raise ValueError(f"suggest must be >= 0, got {suggest}")
    diagnosis = _diagnose(display, graph.catalog, graph.out_of_scope, graph.resolver, graph.aliases)
    if suggest and diagnosis.reason == "missing":
        return replace(diagnosis, candidates=suggest_notes(display, graph.catalog, suggest))
    return diagnosis


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
        resolver: Resolver | None = None,
        aliases: dict[str, str] | None = None,
        link_counts: dict[str, int] | None = None,
        alias_resolved: int = 0,
    ) -> None:
        self.nodes = nodes
        self.out_links = out_links
        self.back_links = back_links
        self.unresolved = unresolved if unresolved is not None else {}
        self.catalog = catalog if catalog is not None else {}
        self.out_of_scope = out_of_scope if out_of_scope is not None else {}
        self.aliases = aliases if aliases is not None else {}
        self.link_counts = link_counts if link_counts is not None else {}
        self.alias_resolved = alias_resolved
        # Retained so diagnose() answers with the same resolver that built the graph; a
        # pluggable Resolver that disagreed with the graph it describes would be worse than none.
        self.resolver: Resolver = resolver if resolver is not None else NormalizeResolver()

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
        aliases = build_aliases(docs, catalog) if config.resolve_aliases else {}

        out_links: dict[str, set[str]] = {rel: set() for rel in nodes}
        back_links: dict[str, set[str]] = {rel: set() for rel in nodes}

        unresolved: dict[str, list[str]] = {}

        # Classification lives in _diagnose so build and the public diagnose() can never disagree
        # about why a link failed. Ambiguous and missing are both broken from a vault-health view;
        # the raw display is recorded once per occurrence, since that is what a human goes and
        # fixes.
        broken = {"ambiguous", "missing"}
        # Every extracted display lands in exactly one bucket. All six keys are seeded so a zero
        # is reported rather than absent — "0 alias-resolved" is a finding, not a non-event.
        link_counts: dict[str, int] = dict.fromkeys(DIAGNOSIS_REASONS, 0)
        alias_resolved = 0
        for doc in docs:
            for display in extractor.extract(doc.text):
                d = _diagnose(display, catalog, out_of_scope, resolver, aliases)
                link_counts[d.reason] += 1
                if d.via == "alias":
                    alias_resolved += 1
                if d.reason in broken:
                    unresolved.setdefault(doc.rel_path, []).append(display)
                elif d.target is not None and d.target != doc.rel_path:
                    out_links[doc.rel_path].add(d.target)

        for src, targets in out_links.items():
            for dst in targets:
                back_links[dst].add(src)

        return cls(
            nodes,
            out_links,
            back_links,
            unresolved,
            catalog,
            out_of_scope,
            resolver,
            aliases,
            link_counts,
            alias_resolved,
        )
