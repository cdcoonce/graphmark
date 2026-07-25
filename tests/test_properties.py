"""Property-based vault generation — Track F's detector.

Every correctness bug in this package's history was found by a human reading link lists from one
vault: seven of them, six in a single day. The frozen differential oracle prevents regression
superbly and has never once surfaced something new, because fixtures only encode shapes somebody
already thought of — and every one of those seven bugs was a shape nobody thought of.

So this file does not check *answers*. It checks the invariants that must hold for any content
whatsoever, over vaults nobody designed. Hypothesis explores the combinations and, on failure,
shrinks to a minimal reproducer instead of handing back a vault to bisect by hand.

`hypothesis` is a dev dependency only; the shipped runtime dependency is still `networkx` alone.
"""

from __future__ import annotations

import tempfile
import unicodedata
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from graphmark.config import VaultConfig
from graphmark.graph import (
    DIAGNOSIS_REASONS,
    NormalizeResolver,
    VaultGraph,
    _normalize,
    _strip_display,
    diagnose,
)
from graphmark.parse import WikilinkExtractor

# Deterministic and bounded: CI time stays sane and a failure reproduces.
SETTINGS = settings(
    max_examples=150,
    deadline=None,
    derandomize=True,
    suppress_health_check=[HealthCheck.too_slow],
)

# Stems chosen to collide under normalization: case, punctuation, spacing and accent variants of a
# tiny pool, so ambiguity and alias contention actually occur rather than being theoretically
# possible. Accented forms are here because #123 (NFD/NFC) was found by inspection, not by test.
STEMS = st.sampled_from(
    [
        "note",
        "Note",
        "no-te",
        "no te",
        "NOTE",
        "café",
        "cafe",
        "a.b",
        "v1.2 release",
        "Índex",
        # Added after the 2026-07-25 pass, in which four defects were found by reading the code and
        # none by this generator — because it drew only from shapes the resolver already handled.
        # Widening the *alphabet* is the fix; each entry below is a class that shipped broken.
        "Phase 2.1",  # #138: a numeric title suffix read as a file extension
        "Standard IEC.61850",  # #138 again, where no length bound separates it from ".md"
        "Q1 — Review",  # #139: non-ASCII punctuation, unfoldable by an ASCII table
        "Charles’ Notes",  # #139: a curly apostrophe against a straight one
        "Q1 - Review",  # the ASCII twin of the above, so the pair can collide
    ]
)
# "work"/"homework" and "docs"/"api-docs" are the #136 shape: one folder name ending with another's,
# which a raw string-suffix match resolved across.
FOLDERS = st.sampled_from(
    [
        "",
        "docs/",
        "docs/deep/",
        "templates/",
        "archive/",
        "one/",
        "two/",
        "work/",
        "homework/",
        "api-docs/",
    ]
)

# Display shapes that have each produced a bug, plus the ordinary ones.
DISPLAY_SUFFIXES = st.sampled_from(
    ["", "|an alias", "#Section", "#^blockref", ".md", ".base", ".canvas", "  |  padded"]
)


@st.composite
def vaults(draw):
    """A vault as {rel_path: file text}, plus the scope config to build it with."""
    n_notes = draw(st.integers(min_value=1, max_value=5))
    notes: dict[str, str] = {}
    for _ in range(n_notes):
        rel = draw(FOLDERS) + draw(STEMS) + ".md"
        aliases = draw(st.lists(STEMS, max_size=2))
        front = ""
        if aliases:
            front = "---\naliases:\n" + "".join(f"  - {a}\n" for a in aliases) + "---\n\n"
        body_links = draw(st.lists(st.tuples(FOLDERS, STEMS, DISPLAY_SUFFIXES), max_size=4))
        body = "\n".join(f"[[{f}{s}{suf}]]" for f, s, suf in body_links)
        # Shapes that must never become edges, mixed in so the suppressed buckets are exercised.
        body += "\n[[#LocalAnchor]]\n`[[InCodeSpan]]`\n```\n[[InFence]]\n```\n"
        # A UTF-8 BOM defeated frontmatter parsing entirely (#137) — aliases vanished and
        # frontmatter links leaked into the body. Generated, so no invariant may assume it away.
        bom = "\ufeff" if draw(st.booleans()) else ""
        notes[rel] = bom + front + body + "\n"
    scoped = draw(st.sampled_from([[], ["docs"], ["docs", "one"]]))
    excluded = draw(st.sampled_from([[], ["archive"], ["templates"]]))
    return notes, scoped, excluded


def _materialize(notes: dict[str, str], root: Path) -> None:
    for rel, text in notes.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def _build(root: Path, scoped: list[str], excluded: list[str], **kw) -> VaultGraph:
    config = VaultConfig(root=root, scoped_folders=scoped, excluded_dirs=excluded, **kw)
    return VaultGraph.build(config, WikilinkExtractor(), NormalizeResolver())


def _assert_no_missing_link_is_known(graph: VaultGraph) -> None:
    """No link the package reports `missing` may name something it already knows.

    Re-derives the verdict per display through the public `diagnose`, because `unresolved` merges
    `ambiguous` with `missing` and an ambiguous display legitimately matches catalog keys.
    """
    for rel, displays in graph.unresolved.items():
        for display in displays:
            if diagnose(graph, display).reason != "missing":
                continue
            key = _normalize(_strip_display(display))
            assert key not in graph.catalog, f"{rel}: [[{display}]] is missing but names a note"
            assert key not in graph.aliases, f"{rel}: [[{display}]] is missing but names an alias"


def _extracted_total(graph: VaultGraph) -> int:
    extractor = WikilinkExtractor()
    return sum(len(extractor.extract(doc.text)) for doc in graph.nodes.values())


@SETTINGS
@given(vaults())
def test_conservation_nothing_vanishes(vault):
    """Every extracted display lands in a bucket. The invariant all seven bugs violated."""
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, scoped, excluded)
        assert sum(graph.link_counts.values()) == _extracted_total(graph)


@SETTINGS
@given(vaults())
def test_every_bucket_is_present_and_non_negative(vault):
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        counts = _build(root, scoped, excluded).link_counts
        assert tuple(counts) == DIAGNOSIS_REASONS
        assert all(v >= 0 for v in counts.values())


@SETTINGS
@given(vaults())
def test_edges_point_at_real_notes_and_never_exceed_resolved(vault):
    """An edge must name a note in the graph, and can only come from a resolved display."""
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, scoped, excluded)
        for src, targets in graph.out_links.items():
            assert src in graph.nodes
            for dst in targets:
                assert dst in graph.nodes
                assert dst != src, "a self-link must never become an edge"
        assert sum(len(v) for v in graph.out_links.values()) <= graph.link_counts["resolved"]


@SETTINGS
@given(vaults())
def test_unresolved_is_exactly_ambiguous_plus_missing(vault):
    """The pre-existing surface and the new tally cannot disagree, on any input."""
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, scoped, excluded)
        occurrences = sum(len(v) for v in graph.unresolved.values())
        assert occurrences == graph.link_counts["ambiguous"] + graph.link_counts["missing"]
        for rel in graph.unresolved:
            assert rel in graph.nodes, "a note outside the graph cannot report broken links"


@SETTINGS
@given(vaults())
def test_back_links_mirror_out_links(vault):
    """The two adjacency maps are one relation seen from both ends."""
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, scoped, excluded)
        forward = {(s, d) for s, ds in graph.out_links.items() for d in ds}
        backward = {(s, d) for d, ss in graph.back_links.items() for s in ss}
        assert forward == backward


@SETTINGS
@given(vaults())
def test_build_is_deterministic(vault):
    """Determinism is this package's headline claim and was asserted nowhere."""
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        first = _build(root, scoped, excluded)
        second = _build(root, scoped, excluded)
        assert first.link_counts == second.link_counts
        assert first.unresolved == second.unresolved
        assert first.catalog == second.catalog
        assert first.aliases == second.aliases
        assert first.out_links == second.out_links
        assert first.alias_resolved == second.alias_resolved


@SETTINGS
@given(vaults())
def test_aliases_never_shadow_a_real_note_name(vault):
    """The anti-hijacking rule, over arbitrary generated collisions."""
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, scoped, excluded)
        for alias_key, target in graph.aliases.items():
            assert alias_key not in graph.catalog, "an alias may never collide with a note name"
            assert target in graph.nodes


@SETTINGS
@given(vaults())
def test_disabling_aliases_only_moves_links_out_of_resolved(vault):
    """Turning a resolution source off may not invent links or change the total."""
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        on = _build(root, scoped, excluded)
        off = _build(root, scoped, excluded, resolve_aliases=False)
        assert sum(on.link_counts.values()) == sum(off.link_counts.values())
        assert off.link_counts["resolved"] <= on.link_counts["resolved"]
        assert off.alias_resolved == 0


# ---------------------------------------------------------------------------
# Metamorphic relations — the properties that target MIS-BUCKETING
# ---------------------------------------------------------------------------
#
# The invariants above are structural: nothing vanishes, edges are real, builds are
# deterministic. They are worth having, but they would have caught NONE of the seven historical
# bugs, because every one of those kept conservation intact — a link was simply filed in the wrong
# bucket. #104 filed a resolvable `[[b.md]]` under `missing`; the buckets still summed correctly.
#
# What catches that is a metamorphic relation: rewrite the vault in a way whose effect on the
# answer is known, and assert the answer changes exactly that much. Obsidian treats `[[X]]`,
# `[[X|alias]]`, `[[X#Section]]` and `[[X.md]]` as the same link, so all four must produce the same
# graph. Each relation below is the general form of a bug that shipped.


def _graph_for(body: str, extra: dict[str, str] | None = None):
    """(counts, edges, unresolved) for a one-note vault plus `extra`.

    The metamorphic relations below compare `[:2]` — counts and edges. The third element is
    deliberately excluded from those comparisons: `unresolved` echoes the *raw* display, which a
    rewrite legitimately changes (`[[X]]` vs `[[X.md]]`), since it is what a human has to go and
    fix in the source note. Comparing it would assert that a rewrite does not rewrite anything.
    """
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        notes = {"src.md": body}
        notes.update(extra or {})
        _materialize(notes, root)
        graph = _build(root, [], [])
        # Snapshot what we compare on; the graph's own paths are inside the temp dir.
        return (
            dict(graph.link_counts),
            {k: sorted(v) for k, v in graph.out_links.items()},
            {k: list(v) for k, v in graph.unresolved.items()},
        )


TARGET = {"target.md": "a note\n"}


@SETTINGS
@given(st.sampled_from(["target", "TARGET", "tar-get", "tar get"]))
def test_md_extension_is_equivalent_to_bare(stem):
    """`[[X.md]]` and `[[X]]` name the same note. The general form of #104."""
    assert _graph_for(f"[[{stem}]]\n", TARGET)[:2] == _graph_for(f"[[{stem}.md]]\n", TARGET)[:2]


@SETTINGS
@given(st.sampled_from(["target", "TARGET", "tar-get"]), st.sampled_from(["shown", "an alias"]))
def test_pipe_alias_is_equivalent_to_bare(stem, shown):
    """`[[X|shown]]` resolves like `[[X]]` — the display text is presentation only."""
    assert (
        _graph_for(f"[[{stem}]]\n", TARGET)[:2] == _graph_for(f"[[{stem}|{shown}]]\n", TARGET)[:2]
    )


@SETTINGS
@given(st.sampled_from(["target", "TARGET"]), st.sampled_from(["Section", "^blockref"]))
def test_anchor_is_equivalent_to_bare(stem, anchor):
    """`[[X#Section]]` resolves like `[[X]]`. The general form of #98's cross-note half."""
    assert (
        _graph_for(f"[[{stem}]]\n", TARGET)[:2] == _graph_for(f"[[{stem}#{anchor}]]\n", TARGET)[:2]
    )


@SETTINGS
@given(st.sampled_from(["  target  ", " target", "target "]))
def test_surrounding_whitespace_is_irrelevant(padded):
    """A column-aligned link names the same note. The bug fixed alongside #107."""
    assert _graph_for("[[target]]\n", TARGET)[:2] == _graph_for(f"[[{padded}]]\n", TARGET)[:2]


@SETTINGS
@given(st.sampled_from(["docs/target   ", "  docs/target", "docs/target      "]))
def test_whitespace_is_irrelevant_on_a_path_qualified_link(padded):
    """The shape the real bug had: a column-aligned table cell, path-qualified.

    Normalization collapses whitespace on its own, so a *bare* padded display resolves either way
    and cannot detect the defect. Only the path-suffix branch — which compares the display against
    rel_paths directly — is sensitive to it, and that is precisely where 13 live links were
    reported broken while pointing at real notes.
    """
    deep = {"docs/target.md": "a note\n"}
    assert _graph_for("[[docs/target]]\n", deep)[:2] == _graph_for(f"[[{padded}]]\n", deep)[:2]


@SETTINGS
@given(st.sampled_from(["Nickname", "nickname", "Nick-name"]))
def test_renaming_a_note_to_its_own_alias_preserves_resolution(alias):
    """A link resolves the same whether the name is the filename or a declared alias.

    The general form of #119: alias resolution and stem resolution must agree, so a vault cannot
    silently lose links by moving a name from one to the other.
    """
    by_stem = _graph_for(f"[[{alias}]]\n", {f"{alias}.md": "a note\n"})
    by_alias = _graph_for(
        f"[[{alias}]]\n", {"other.md": f"---\naliases:\n  - {alias}\n---\n\na note\n"}
    )
    assert by_stem[0] == by_alias[0], "same counts whether the name is a stem or an alias"


@SETTINGS
@given(st.sampled_from(["Chart.base", "Board.canvas", "diagram.png"]))
def test_a_non_note_target_is_never_counted_as_missing(display):
    """The general form of #101: an unindexed file type is out of scope, not broken."""
    counts, _, unresolved = _graph_for(f"[[{display}]]\n")
    assert counts["missing"] == 0
    assert counts["non-note-file"] == 1
    assert unresolved == {}


@SETTINGS
@given(st.sampled_from(["#Section", "#^abc123", "#Design cruxes|crux"]))
def test_an_intra_note_reference_is_never_counted_as_missing(display):
    """The general form of #98: a same-note reference targets no note at all."""
    counts, _, unresolved = _graph_for(f"[[{display}]]\n")
    assert counts["missing"] == 0
    assert counts["intra-note"] == 1
    assert unresolved == {}


@SETTINGS
@given(vaults())
def test_no_missing_link_names_something_the_resolver_knows(vault):
    """The Track F invariant: `missing` and "the package knows this name" cannot both be true.

    Under correct behavior such a link would have resolved, so this is an internal-consistency
    assertion rather than a heuristic — no thresholds, no calibration, and no false-positive mode.

    It catches the *class* #119 belonged to rather than its symptom: any future regression in alias
    lookup, normalization or the catalog itself surfaces as a link the package simultaneously claims
    not to know and does know. Chosen over the four statistical heuristics #127 proposed because
    those were measured and fire constantly on healthy vaults — see #133 for the numbers.
    """
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, scoped, excluded)
        _assert_no_missing_link_is_known(graph)


@SETTINGS
@given(vaults())
def test_the_invariant_holds_with_aliases_disabled(vault):
    """With the feature off the alias map is empty, so the catalog half still applies.

    The alias half is then vacuous rather than wrong — which is the distinction between the
    documented `resolve_aliases=False` opt-out and a genuine regression in the lookup.
    """
    notes, scoped, excluded = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, scoped, excluded, resolve_aliases=False)
        assert graph.aliases == {}
        _assert_no_missing_link_is_known(graph)


def test_the_invariant_fails_when_alias_lookup_regresses(monkeypatch):
    """Teeth: break the lookup while the map is still built, and the assertion must catch it.

    This is the #119 shape exactly — `build_aliases` still runs and `graph.aliases` is still
    populated, but the classifier stops consulting it, so links written against a live alias are
    reported `missing`. Without this test the invariant above could be vacuously true.
    """
    from graphmark import graph as graph_mod

    original = graph_mod._diagnose
    monkeypatch.setattr(
        graph_mod,
        "_diagnose",
        lambda display, catalog, oos, resolver, aliases=None: original(
            display, catalog, oos, resolver, None
        ),
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(
            {
                "Target.md": "---\naliases:\n  - TGT\n---\n\nbody\n",
                "src.md": "[[TGT]]\n",
            },
            root,
        )
        graph = _build(root, [], [])
        assert graph.aliases, "the map must still be built, or this proves nothing"
        assert graph.link_counts["missing"] == 1
        with pytest.raises(AssertionError):
            _assert_no_missing_link_is_known(graph)


# ---------------------------------------------------------------------------------------------
# Round-trip generation: the half the invariants above cannot reach.
#
# Measured on 2026-07-25: with #136, #137 and #139 reverted one at a time, every invariant above
# stayed green. They are conservation and self-consistency properties, and each of those bugs is
# perfectly self-consistent — #136's fabricated edge IS in the graph, so nothing vanishes; a BOM'd
# note simply has no frontmatter, which is consistent; a link the normalizer cannot match is
# genuinely missing by the package's own rules. Self-consistency cannot see a wrong answer.
#
# What is missing is an *oracle*: a link whose intended target is known independently of what the
# resolver says. So these build a note first and then write a link derived from it by a
# transformation Obsidian treats as identity-preserving. The expected answer is known by
# construction, and any transformation the package mishandles fails immediately.
# ---------------------------------------------------------------------------------------------

#: Ways to write a link that must still name the same note. Each is a documented equivalence —
#: Obsidian resolves all of them, and several are exactly where a defect has already been found.
TRANSFORMS = st.sampled_from(
    [
        "identity",
        "upper",
        "lower",
        "md_suffix",  # [[Note.md]]
        "anchor",  # [[Note#Section]]
        "alias_display",  # [[Note|whatever]]
        "padded",  # [[  Note  ]]
        "nfd",  # #123: the form macOS stores filenames in
        "nfc",  # #123: the form an editor emits
        "hyphens_to_spaces",  # the normalizer's documented punctuation folding
        "spaces_to_hyphens",
        "path_qualified",  # [[folder/Note]] — #136's territory
        "ascii_punct_twin",  # #139: the em-dash/curly-quote title typed with ASCII
    ]
)

#: Non-ASCII marks and the ASCII characters a human types instead. Obsidian's own switcher matches
#: across these, and so must the normalizer — #139 was exactly this gap.
ASCII_TWINS = {"—": "-", "–": "-", "’": "'", "“": '"', "”": '"', "…": "..."}


def _ascii_punct_twin(text: str) -> str:
    for fancy, plain in ASCII_TWINS.items():
        text = text.replace(fancy, plain)
    return text


#: Folder sets a single generated vault draws from. Each pool is small so its notes actually
#: collide, and the first three are the pairs where one name ends with another's — the shape #136
#: resolved across.
FOLDER_POOLS = st.sampled_from(
    [
        ["work/", "homework/"],
        ["docs/", "api-docs/"],
        ["one/", "one/two/"],
        [""],
        ["", "docs/"],
        ["docs/", "docs/deep/"],
        ["archive/", "templates/"],
    ]
)


def _components(name: str) -> list[str]:
    """Normalized path components, `.md` dropped — the spec's notion of "names this note".

    Written from the documented behavior rather than by calling the resolver's helpers, so it is an
    independent check and not a restatement of the implementation.
    """
    name = name.removesuffix(".md") if name.lower().endswith(".md") else name
    return [_normalize(part) for part in name.split("/") if part]


def _apply_transform(rel: str, kind: str) -> str:
    """Rewrite a note's rel_path into a link display that must still name it."""
    stem = Path(rel).stem
    parent = Path(rel).parent.as_posix()
    if kind == "upper":
        return stem.upper()
    if kind == "lower":
        return stem.lower()
    if kind == "md_suffix":
        return f"{stem}.md"
    if kind == "anchor":
        return f"{stem}#Some Section"
    if kind == "alias_display":
        return f"{stem}|a display"
    if kind == "padded":
        return f"  {stem}  "
    if kind == "nfd":
        return unicodedata.normalize("NFD", stem)
    if kind == "nfc":
        return unicodedata.normalize("NFC", stem)
    if kind == "hyphens_to_spaces":
        return stem.replace("-", " ")
    if kind == "spaces_to_hyphens":
        return stem.replace(" ", "-")
    if kind == "path_qualified" and parent != ".":
        return f"{parent}/{stem}"
    if kind == "ascii_punct_twin":
        return _ascii_punct_twin(stem)
    return stem


@st.composite
def vaults_with_known_links(draw):
    """A vault where every link was derived from a note that exists, plus the intended targets."""
    # Narrow per-vault pools, drawn first. Sampling each note independently from the full alphabet
    # spreads a 4-note vault across 10 folders and 15 stems, so the *collisions* that matter almost
    # never co-occur — with the wide pools, reverting #136 left this property green. FOLDER_POOLS
    # deliberately includes the suffix-colliding pair that defect turned on.
    folders = draw(FOLDER_POOLS)
    stems = draw(st.lists(STEMS, min_size=1, max_size=3, unique=True))

    # Deduped case- and form-insensitively, not just by string: macOS is case-insensitive and may
    # normalize, so "note.md" and "Note.md" would land on ONE file and the oracle would claim a
    # note exists that does not. This is a property of the filesystem under test, not of graphmark.
    drawn = [f + s + ".md" for f in folders for s in stems]
    seen: set[str] = set()
    rels = []
    for rel in sorted(drawn):
        key = unicodedata.normalize("NFC", rel).casefold()
        if key not in seen:
            seen.add(key)
            rels.append(rel)

    intents: list[tuple[str, str]] = []  # (display, intended rel_path)
    notes = {rel: "body\n" for rel in rels}

    for index, rel in enumerate(rels):
        for _ in range(draw(st.integers(min_value=0, max_value=2))):
            intents.append((_apply_transform(rel, draw(TRANSFORMS)), rel))

        # An alias, optionally on a BOM'd note. That pairing is the point: a BOM defeats frontmatter
        # parsing entirely (#137), so the alias silently stops existing — a shape no generator whose
        # notes have no frontmatter can reach.
        if draw(st.booleans()):
            # Keyed by index so uniqueness is structural. Deriving the alias from the note's name
            # made two notes declare aliases that *normalize* to one key ("no te" / "no-te"), which
            # build_aliases correctly refuses to resolve — the oracle would then be wrong, not the
            # package. The alias text is not what is under test; the alias mechanism is.
            alias = f"alias number {index}"
            bom = "﻿" if draw(st.booleans()) else ""
            notes[rel] = f"{bom}---\naliases:\n  - {alias}\n---\n\nbody\n"
            if draw(st.booleans()):
                intents.append((alias, rel))

    notes["source.md"] = "".join(f"[[{d}]]\n" for d, _ in intents)
    return notes, intents


@SETTINGS
@given(vaults_with_known_links())
def test_a_link_written_from_an_existing_note_names_that_note(vault):
    """The oracle property: an identity-preserving rewrite must not break resolution.

    A genuine collision is a legitimate refusal, so an `ambiguous` verdict passes **only** when the
    intended note is among the candidates the resolver saw. That keeps the property from being
    satisfiable by declining everything.
    """
    notes, intents = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, [], [])
        for display, intended in intents:
            d = diagnose(graph, display)
            if d.reason == "ambiguous":
                assert intended in d.candidates, (
                    f"[[{display}]] was declined as ambiguous without {intended} among "
                    f"the candidates {d.candidates}"
                )
                # An ambiguity must be real. Every candidate has to be a note the display actually
                # names, component-wise — a spurious extra match is how #136 turned a correct link
                # into a reported break, and a candidate set checked only for membership hides it.
                wanted = _components(_strip_display(display))
                for candidate in d.candidates:
                    have = _components(candidate)
                    assert have[-len(wanted) :] == wanted, (
                        f"[[{display}]] was declined as ambiguous against {candidate}, "
                        f"which it does not name"
                    )
                continue
            assert d.reason == "resolved", f"[[{display}]] should name {intended}, got {d.reason}"
            assert d.target == intended, f"[[{display}]] resolved to {d.target}, not {intended}"


@SETTINGS
@given(vaults_with_known_links())
def test_a_link_written_from_an_existing_note_is_never_counted_broken(vault):
    """The same guarantee at the level of the number the CI gate reports."""
    notes, intents = vault
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _materialize(notes, root)
        graph = _build(root, [], [])
        assert graph.link_counts["missing"] == 0, graph.unresolved
        assert graph.link_counts["non-note-file"] == 0, graph.unresolved


#: Names deliberately absent from the generated vaults. Numbered titles are here because a decimal
#: suffix was read as a file extension and the link vanished from the health count (#138) — a
#: *false negative*, which no conservation property can see.
ABSENT_NAMES = st.sampled_from(
    [
        "Nothing Named This",
        "Meeting 3.5",
        "Phase 9.4",
        "Spec v0.9",
        "Budget FY26.2",
        "Standard IEC.61850",
        "Ghost — Note",
    ]
)


@SETTINGS
@given(vaults_with_known_links(), st.lists(ABSENT_NAMES, min_size=1, max_size=3))
def test_a_link_to_a_note_that_does_not_exist_is_reported_missing(vault, absent):
    """The negative oracle: a broken link must reach the count, not a suppressing bucket.

    Every previous defect class inflated the broken-link number; #138 deflated it, by filing a
    genuine break under `non-note-file`. An undercount is invisible by construction and reads as
    health, so it needs an oracle of its own — a name known not to exist.
    """
    notes, _ = vault
    absent = [name for name in absent if name.lower() not in {Path(r).stem.lower() for r in notes}]
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        notes = dict(notes)
        notes["broken.md"] = "".join(f"[[{name}]]\n" for name in absent)
        _materialize(notes, root)
        graph = _build(root, [], [])
        for name in absent:
            reason = diagnose(graph, name).reason
            assert reason == "missing", f"[[{name}]] does not exist but was filed as {reason}"
        assert graph.link_counts["missing"] >= len(absent)
