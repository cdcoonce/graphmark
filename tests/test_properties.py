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
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from graphmark.config import VaultConfig
from graphmark.graph import DIAGNOSIS_REASONS, NormalizeResolver, VaultGraph
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
    ["note", "Note", "no-te", "no te", "NOTE", "café", "cafe", "a.b", "v1.2 release", "Índex"]
)
FOLDERS = st.sampled_from(["", "docs/", "docs/deep/", "templates/", "archive/", "one/", "two/"])

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
        notes[rel] = front + body + "\n"
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
