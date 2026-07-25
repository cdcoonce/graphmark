"""VaultGraph.unresolved — links that resolved to nothing, recorded instead of dropped.

build() previously discarded every unresolvable link silently, so "how many broken links does
this vault have" — the flagship `graphmark check` threshold and the one vault-health signal
ordinary link checkers already cover — was uncomputable from any graphmark surface.

The reference engine never emitted this, so these semantics are graphmark's own (Track B,
human-confirmable):
  1. an AMBIGUOUS bare link counts as unresolved (the Resolver returns None for both cases, and
     both are equally broken from a vault-health point of view);
  2. a resolved SELF-link does NOT count (it resolved; it is merely not an edge);
  3. every OCCURRENCE counts — three [[Missing]] links in one note contribute three.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **kwargs), WikilinkExtractor(), NormalizeResolver()
    )


def _total(graph: VaultGraph) -> int:
    return sum(len(v) for v in graph.unresolved.values())


class TestUnresolvedBasics:
    def test_a_link_to_a_missing_note_is_recorded(self, tmp_path):
        _write(tmp_path, "a.md", "Points at [[Nowhere]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {"a.md": ["Nowhere"]}

    def test_a_resolvable_link_is_not_recorded(self, tmp_path):
        _write(tmp_path, "a.md", "Points at [[b]].\n")
        _write(tmp_path, "b.md", "Target.\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}

    def test_notes_without_unresolved_links_are_absent_from_the_mapping(self, tmp_path):
        _write(tmp_path, "clean.md", "No links.\n")
        _write(tmp_path, "broken.md", "A [[Missing]] link.\n")
        graph = _build(tmp_path)
        assert set(graph.unresolved) == {"broken.md"}

    def test_empty_vault_has_no_unresolved(self, tmp_path):
        vault = tmp_path / "empty"
        vault.mkdir()
        assert _build(vault).unresolved == {}

    def test_display_is_recorded_raw_before_alias_and_anchor_stripping(self, tmp_path):
        # The raw display is what a human has to go fix in the source note.
        _write(tmp_path, "a.md", "See [[Missing|the alias]] and [[Gone#Section]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved["a.md"] == ["Missing|the alias", "Gone#Section"]


class TestUnresolvedSemantics:
    """The three decisions the reference engine never made for us."""

    def test_ambiguous_bare_link_counts_as_unresolved(self, tmp_path):
        # Two notes share the stem "note", so a bare [[note]] cannot resolve.
        _write(tmp_path, "one/note.md", "")
        _write(tmp_path, "two/note.md", "")
        _write(tmp_path, "src.md", "Ambiguous [[note]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {"src.md": ["note"]}

    def test_resolved_self_link_does_not_count(self, tmp_path):
        # [[solo]] from solo.md RESOLVES (to itself) — build drops it as an edge, but it is
        # not a broken link and must not inflate the unresolved count.
        _write(tmp_path, "solo.md", "I link to [[solo]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["solo.md"] == set()

    def test_every_occurrence_counts(self, tmp_path):
        _write(tmp_path, "a.md", "[[Missing]] then [[Missing]] then [[Missing]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved["a.md"] == ["Missing", "Missing", "Missing"]
        assert _total(graph) == 3

    def test_extraction_order_is_preserved(self, tmp_path):
        _write(tmp_path, "a.md", "[[Zeta]] then [[Alpha]] then [[Mid]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved["a.md"] == ["Zeta", "Alpha", "Mid"]


class TestUnresolvedIntegration:
    def test_filtered_notes_contribute_no_unresolved_links(self, tmp_path):
        # A rules file or excluded-dir note is not part of the vault, so its broken links
        # must not show up in the vault's health numbers.
        _write(tmp_path, "keep.md", "")
        _write(tmp_path, "CLAUDE.md", "Rules linking [[Nowhere]].\n")
        _write(tmp_path, "archive/old.md", "Archived [[AlsoNowhere]].\n")
        graph = _build(tmp_path, excluded_dirs=["archive"])
        assert graph.unresolved == {}

    def test_links_inside_code_spans_are_not_unresolved(self, tmp_path):
        _write(tmp_path, "a.md", "Inline `[[NotALink]]` and:\n\n```\n[[AlsoNot]]\n```\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}

    def test_directly_constructed_graph_defaults_to_empty_unresolved(self):
        # Back-compatible construction: existing callers pass three arguments.
        graph = VaultGraph(nodes={}, out_links={}, back_links={})
        assert graph.unresolved == {}

    @pytest.mark.parametrize("fixture", ["simple", "alt"])
    def test_frozen_fixtures_expose_unresolved_without_changing_other_metrics(self, fixture):
        from graphmark.config import load_config
        from graphmark.metrics import stats

        cfg = load_config(Path(__file__).parent / "fixtures" / fixture / "config.toml")
        graph = VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())
        assert isinstance(graph.unresolved, dict)
        # stats is untouched by this addition — the oracle still governs it.
        assert set(stats(graph)) == {"notes", "edges", "orphans", "clusters", "density"}


class TestIntraNoteAnchorLinks:
    """[[#Heading]] is a same-note reference, not a link to another note.

    It is neither an edge nor a broken link, so counting it as unresolved inflates the
    check gate's max_unresolved_links threshold (measured: 19% of a real vault's total).
    """

    def test_anchor_only_link_is_not_unresolved(self, tmp_path):
        _write(tmp_path, "a.md", "# Top\n\nJump to [[#Section]].\n\n## Section\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}

    def test_anchor_only_link_with_alias_is_not_unresolved(self, tmp_path):
        _write(tmp_path, "a.md", "See [[#Design cruxes|crux 2]].\n")
        assert _build(tmp_path).unresolved == {}

    def test_block_reference_is_not_unresolved(self, tmp_path):
        _write(tmp_path, "a.md", "See [[#^abc123]].\n")
        assert _build(tmp_path).unresolved == {}

    def test_anchor_only_link_creates_no_edge(self, tmp_path):
        _write(tmp_path, "a.md", "Jump to [[#Section]].\n")
        graph = _build(tmp_path)
        assert graph.out_links["a.md"] == set()

    def test_whitespace_only_display_is_ignored(self, tmp_path):
        _write(tmp_path, "a.md", "Odd [[   ]] link.\n")
        assert _build(tmp_path).unresolved == {}

    def test_cross_note_anchor_still_resolves(self, tmp_path):
        _write(tmp_path, "a.md", "See [[b#Section]].\n")
        _write(tmp_path, "b.md", "# B\n\n## Section\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["a.md"] == {"b.md"}

    def test_cross_note_anchor_to_a_missing_note_is_still_unresolved(self, tmp_path):
        _write(tmp_path, "a.md", "See [[Nowhere#Section]].\n")
        assert _build(tmp_path).unresolved == {"a.md": ["Nowhere#Section"]}

    def test_mixed_note_keeps_only_the_real_break(self, tmp_path):
        _write(tmp_path, "a.md", "[[#Local]] and [[Missing]] and [[#Other|x]].\n")
        assert _build(tmp_path).unresolved == {"a.md": ["Missing"]}


class TestNonMarkdownTargets:
    """A link to a file graphmark does not index is out of scope, not broken.

    Obsidian wikilinks legitimately target Bases (.base), Canvas (.canvas), images and PDFs.
    graphmark only indexes *.md, so it has no basis to call those links broken — on a real
    vault they were 10% of the reported total, every one of them a working link.
    """

    @pytest.mark.parametrize(
        "display",
        [
            "Stale Side-Projects.base",
            "Board.canvas",
            "diagram.png",
            "spec.pdf",
            "sketch.excalidraw",
            "People Missing Context.base|People Missing Context",
            "Board.canvas#Section",
        ],
    )
    def test_non_markdown_target_is_not_unresolved(self, tmp_path, display):
        _write(tmp_path, "a.md", f"See [[{display}]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["a.md"] == set()

    def test_md_targets_are_exempt_from_the_rule(self, tmp_path):
        # .md is excluded from the non-note rule, so a link ending in .md is left to the
        # resolver — which now resolves it (a trailing ".md" is stripped, matching Obsidian).
        _write(tmp_path, "a.md", "See [[b.md]].\n")
        _write(tmp_path, "b.md", "Target.\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["a.md"] == {"b.md"}

    def test_missing_md_target_is_still_unresolved(self, tmp_path):
        _write(tmp_path, "a.md", "See [[Nowhere.md]].\n")
        assert _build(tmp_path).unresolved == {"a.md": ["Nowhere.md"]}

    def test_dotted_title_is_not_mistaken_for_a_file_extension(self, tmp_path):
        # "v1.2 release notes" has spaces after the dot — it is a note title, so a missing
        # one must still be reported.
        _write(tmp_path, "a.md", "See [[v1.2 release notes]].\n")
        assert _build(tmp_path).unresolved == {"a.md": ["v1.2 release notes"]}

    def test_a_resolvable_dotted_note_is_never_suppressed(self, tmp_path):
        # The rule only applies after the resolver fails, so a real note wins.
        _write(tmp_path, "a.md", "See [[report.v2]].\n")
        _write(tmp_path, "report.v2.md", "Target.\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["a.md"] == {"report.v2.md"}

    def test_mixed_note_keeps_only_the_missing_note(self, tmp_path):
        _write(tmp_path, "a.md", "[[Chart.base]] and [[Missing]] and [[#local]].\n")
        assert _build(tmp_path).unresolved == {"a.md": ["Missing"]}


class TestPaddedDisplays:
    """Whitespace around the note part must not stop a link from resolving.

    Real vaults contain column-aligned tables — ``[[folder/note        | alias]]`` — where the
    note part carries trailing spaces. Both resolution branches now see the stripped display
    (13 such links on a live vault were reported broken while pointing at real notes).
    """

    def test_padded_bare_display_resolves(self, tmp_path):
        _write(tmp_path, "a.md", "See [[ b  | the alias]].\n")
        _write(tmp_path, "b.md", "Target.\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["a.md"] == {"b.md"}

    def test_padded_path_qualified_display_resolves(self, tmp_path):
        _write(tmp_path, "a.md", "See [[docs/b     | the alias]].\n")
        _write(tmp_path, "docs/b.md", "Target.\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["a.md"] == {"docs/b.md"}

    def test_padded_md_extension_still_strips(self, tmp_path):
        _write(tmp_path, "a.md", "See [[b.md  | alias]].\n")
        _write(tmp_path, "b.md", "Target.\n")
        assert _build(tmp_path).out_links["a.md"] == {"b.md"}

    def test_a_padded_missing_note_is_still_unresolved(self, tmp_path):
        _write(tmp_path, "a.md", "See [[ Nowhere  | alias]].\n")
        assert _build(tmp_path).unresolved == {"a.md": [" Nowhere  | alias"]}


class TestOutOfScopeNoteTargets:
    """A link to a note that exists but is out of graph scope is out of scope, not broken.

    build() drops unscoped folders, excluded dirs and rules files from the catalog and then
    forgets they exist, so links to them fail the resolver. The link is correct — Obsidian
    follows it — it just points somewhere graphmark deliberately does not index. On a real
    vault these were 7% of the reported total ([[CLAUDE]], [[AGENTS]], a templates/ note).

    Consulted only AFTER the resolver fails, so nothing that resolves in-graph is affected.
    """

    def test_link_to_a_rules_file_is_not_unresolved(self, tmp_path):
        _write(tmp_path, "notes/a.md", "See [[CLAUDE]].\n")
        _write(tmp_path, "CLAUDE.md", "Rules.\n")
        graph = _build(tmp_path, rules_files=["CLAUDE.md"])
        assert graph.unresolved == {}
        assert graph.out_links["notes/a.md"] == set()

    def test_link_into_an_unscoped_folder_is_not_unresolved(self, tmp_path):
        _write(tmp_path, "docs/a.md", "See [[Intake Guide]].\n")
        _write(tmp_path, "templates/Intake Guide.md", "Template.\n")
        assert _build(tmp_path, scoped_folders=["docs"]).unresolved == {}

    def test_link_into_an_excluded_dir_is_not_unresolved(self, tmp_path):
        _write(tmp_path, "a.md", "See [[old thing]].\n")
        _write(tmp_path, "archive/old thing.md", "Archived.\n")
        assert _build(tmp_path, excluded_dirs=["archive"]).unresolved == {}

    @pytest.mark.parametrize(
        "display",
        ["CLAUDE", "claude", "CLAUDE|the rules", "CLAUDE#Non-negotiables", "CLAUDE.md"],
    )
    def test_alias_anchor_case_and_md_forms_all_suppress(self, tmp_path, display):
        _write(tmp_path, "notes/a.md", f"See [[{display}]].\n")
        _write(tmp_path, "CLAUDE.md", "Rules.\n")
        assert _build(tmp_path, rules_files=["CLAUDE.md"]).unresolved == {}

    def test_path_qualified_link_to_an_out_of_scope_note_is_not_unresolved(self, tmp_path):
        _write(tmp_path, "docs/a.md", "See [[templates/data/Intake Guide]].\n")
        _write(tmp_path, "templates/data/Intake Guide.md", "Template.\n")
        assert _build(tmp_path, scoped_folders=["docs"]).unresolved == {}

    def test_an_ambiguous_out_of_scope_stem_still_suppresses(self, tmp_path):
        # Out-of-scope notes are never link targets, so ambiguity among them says nothing
        # about whether the in-graph link is broken. Any candidate suppresses.
        _write(tmp_path, "docs/a.md", "See [[shared]].\n")
        _write(tmp_path, "templates/one/shared.md", "")
        _write(tmp_path, "templates/two/shared.md", "")
        assert _build(tmp_path, scoped_folders=["docs"]).unresolved == {}

    def test_a_note_that_exists_nowhere_is_still_unresolved(self, tmp_path):
        _write(tmp_path, "docs/a.md", "See [[Nowhere]].\n")
        _write(tmp_path, "templates/Something Else.md", "")
        assert _build(tmp_path, scoped_folders=["docs"]).unresolved == {"docs/a.md": ["Nowhere"]}

    def test_an_in_scope_note_still_wins_over_an_out_of_scope_namesake(self, tmp_path):
        # The rule only applies after the resolver fails, so the real in-graph note wins and
        # keeps its edge.
        _write(tmp_path, "docs/a.md", "See [[guide]].\n")
        _write(tmp_path, "docs/guide.md", "In scope.\n")
        _write(tmp_path, "templates/guide.md", "Out of scope.\n")
        graph = _build(tmp_path, scoped_folders=["docs"])
        assert graph.unresolved == {}
        assert graph.out_links["docs/a.md"] == {"docs/guide.md"}

    def test_mixed_note_keeps_only_the_real_break(self, tmp_path):
        _write(tmp_path, "docs/a.md", "[[Intake Guide]] and [[Missing]].\n")
        _write(tmp_path, "templates/Intake Guide.md", "Template.\n")
        assert _build(tmp_path, scoped_folders=["docs"]).unresolved == {"docs/a.md": ["Missing"]}
