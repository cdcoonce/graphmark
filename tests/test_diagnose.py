"""diagnose() — why a link failed, not just that it did.

build() already sorts every wikilink into one of six outcomes and then discards five of them; only
"it ended up in unresolved" escaped, which conflates an ambiguous link with a missing one. Those
need different repairs: an ambiguous link needs disambiguating against the notes it collided with,
a missing one needs creating or deleting. Consumers that need the distinction had no choice but to
reimplement resolution, which is the drift Track E exists to end.

build() is refactored to route its own classification through this function — two independent
classifiers inside the package would recreate the very problem being fixed, so the property test
at the bottom of this file pins them together.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphmark.config import VaultConfig
from graphmark.graph import LinkDiagnosis, NormalizeResolver, VaultGraph, diagnose
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestResolved:
    def test_a_resolvable_link_reports_its_target(self, tmp_path):
        _write(tmp_path, "b.md")
        d = diagnose(_build(tmp_path), "b")
        assert d == LinkDiagnosis(display="b", target="b.md", reason="resolved", candidates=())

    def test_the_target_carries_the_canonical_title(self, tmp_path):
        # The repair the gardener needs: [[ethan courtman]] → [[Ethan Courtman]]. The caller
        # recovers the title from the target's stem, so no separate title field is needed.
        _write(tmp_path, "people/Ethan Courtman.md")
        d = diagnose(_build(tmp_path), "ethan courtman")
        assert d.reason == "resolved"
        assert Path(d.target).stem == "Ethan Courtman"

    def test_path_qualified_link_resolves(self, tmp_path):
        _write(tmp_path, "docs/deep/note.md")
        d = diagnose(_build(tmp_path), "deep/note")
        assert (d.reason, d.target) == ("resolved", "docs/deep/note.md")

    def test_a_self_link_is_resolved_not_broken(self, tmp_path):
        _write(tmp_path, "solo.md", "I link to [[solo]].\n")
        d = diagnose(_build(tmp_path), "solo")
        assert (d.reason, d.target) == ("resolved", "solo.md")


class TestAmbiguous:
    def test_a_colliding_bare_link_is_ambiguous_with_every_candidate(self, tmp_path):
        _write(tmp_path, "one/note.md")
        _write(tmp_path, "two/note.md")
        d = diagnose(_build(tmp_path), "note")
        assert d.reason == "ambiguous"
        assert d.target is None
        assert d.candidates == ("one/note.md", "two/note.md")

    def test_candidates_are_sorted(self, tmp_path):
        for rel in ("zeta/note.md", "alpha/note.md", "mid/note.md"):
            _write(tmp_path, rel)
        assert diagnose(_build(tmp_path), "note").candidates == (
            "alpha/note.md",
            "mid/note.md",
            "zeta/note.md",
        )

    def test_an_ambiguous_path_suffix_is_ambiguous(self, tmp_path):
        _write(tmp_path, "a/deep/note.md")
        _write(tmp_path, "b/deep/note.md")
        d = diagnose(_build(tmp_path), "deep/note")
        assert d.reason == "ambiguous"
        assert d.candidates == ("a/deep/note.md", "b/deep/note.md")


class TestSuppressedReasons:
    def test_an_intra_note_reference_is_named_as_such(self, tmp_path):
        _write(tmp_path, "a.md")
        d = diagnose(_build(tmp_path), "#Some Heading")
        assert (d.reason, d.target, d.candidates) == ("intra-note", None, ())

    def test_a_block_reference_is_intra_note(self, tmp_path):
        _write(tmp_path, "a.md")
        assert diagnose(_build(tmp_path), "#^abc123").reason == "intra-note"

    @pytest.mark.parametrize("display", ["Chart.base", "Board.canvas", "diagram.png", "spec.pdf"])
    def test_a_non_note_file_is_named_as_such(self, tmp_path, display):
        _write(tmp_path, "a.md")
        d = diagnose(_build(tmp_path), display)
        assert (d.reason, d.target) == ("non-note-file", None)

    def test_an_out_of_scope_note_is_named_as_such(self, tmp_path):
        _write(tmp_path, "notes/a.md")
        _write(tmp_path, "CLAUDE.md")
        d = diagnose(_build(tmp_path, rules_files=["CLAUDE.md"]), "CLAUDE")
        assert d.reason == "out-of-scope-note"
        assert d.target is None
        assert d.candidates == ("CLAUDE.md",)

    def test_an_out_of_scope_note_carries_every_candidate(self, tmp_path):
        _write(tmp_path, "docs/a.md")
        _write(tmp_path, "templates/one/shared.md")
        _write(tmp_path, "templates/two/shared.md")
        d = diagnose(_build(tmp_path, scoped_folders=["docs"]), "shared")
        assert d.reason == "out-of-scope-note"
        assert d.candidates == ("templates/one/shared.md", "templates/two/shared.md")

    def test_a_note_that_exists_nowhere_is_missing(self, tmp_path):
        _write(tmp_path, "a.md")
        d = diagnose(_build(tmp_path), "Nowhere")
        assert (d.reason, d.target, d.candidates) == ("missing", None, ())

    def test_an_in_scope_note_beats_an_out_of_scope_namesake(self, tmp_path):
        _write(tmp_path, "docs/guide.md")
        _write(tmp_path, "templates/guide.md")
        d = diagnose(_build(tmp_path, scoped_folders=["docs"]), "guide")
        assert (d.reason, d.target) == ("resolved", "docs/guide.md")


class TestDisplayForms:
    """Alias, anchor and .md forms name the same note, so they must diagnose identically."""

    @pytest.mark.parametrize(
        "display", ["b", "b|an alias", "b#Section", "b.md", "b.MD", " b  | padded"]
    )
    def test_every_form_of_a_resolvable_link_resolves(self, tmp_path, display):
        _write(tmp_path, "b.md")
        d = diagnose(_build(tmp_path), display)
        assert (d.reason, d.target) == ("resolved", "b.md")

    def test_the_raw_display_is_echoed_verbatim(self, tmp_path):
        # The caller has to print what a human must go fix, so the display must not be normalized.
        _write(tmp_path, "a.md")
        assert diagnose(_build(tmp_path), "Nowhere|the alias").display == "Nowhere|the alias"

    @pytest.mark.parametrize("display", ["Missing|alias", "Missing#Section", "Missing.md"])
    def test_every_form_of_a_missing_link_is_missing(self, tmp_path, display):
        _write(tmp_path, "a.md")
        assert diagnose(_build(tmp_path), display).reason == "missing"


class TestReasonSurface:
    def test_the_reason_set_is_closed(self, tmp_path):
        # A consumer switches on these strings, so the set is part of the contract.
        from graphmark.graph import DIAGNOSIS_REASONS

        assert DIAGNOSIS_REASONS == (
            "resolved",
            "ambiguous",
            "non-note-file",
            "out-of-scope-note",
            "missing",
            "intra-note",
        )

    def test_diagnosis_is_immutable(self, tmp_path):
        _write(tmp_path, "a.md")
        d = diagnose(_build(tmp_path), "Nowhere")
        with pytest.raises(AttributeError):
            d.reason = "resolved"  # type: ignore[misc]

    def test_exported_from_the_top_level(self):
        import graphmark

        assert graphmark.diagnose is diagnose
        assert graphmark.LinkDiagnosis is LinkDiagnosis


class TestBuildAgreement:
    """build() must route its own classification through diagnose, not merely agree with it."""

    def test_unresolved_is_exactly_the_ambiguous_and_missing_displays(self, tmp_path):
        # One vault exercising all six outcomes at once.
        _write(
            tmp_path,
            "docs/hub.md",
            "\n".join(
                [
                    "[[target]]",  # resolved
                    "[[note]]",  # ambiguous
                    "[[Chart.base]]",  # non-note-file
                    "[[CLAUDE]]",  # out-of-scope note
                    "[[Nowhere]]",  # missing
                    "[[#Local]]",  # intra-note
                    "[[docs/deep/note]]",  # resolved, path-qualified
                ]
            )
            + "\n",
        )
        _write(tmp_path, "docs/target.md")
        _write(tmp_path, "docs/one/note.md")
        _write(tmp_path, "docs/two/note.md")
        _write(tmp_path, "docs/deep/note.md")
        _write(tmp_path, "CLAUDE.md")
        graph = _build(tmp_path, scoped_folders=["docs"], rules_files=["CLAUDE.md"])

        broken = {"ambiguous", "missing"}
        expected = [
            display
            for display in WikilinkExtractor().extract((tmp_path / "docs/hub.md").read_text())
            if diagnose(graph, display).reason in broken
        ]
        assert graph.unresolved["docs/hub.md"] == expected
        assert expected == ["note", "Nowhere"]

    def test_edges_are_exactly_the_resolved_non_self_targets(self, tmp_path):
        _write(tmp_path, "hub.md", "[[a]] [[b]] [[hub]] [[Nowhere]] [[Chart.base]]\n")
        _write(tmp_path, "a.md")
        _write(tmp_path, "b.md")
        graph = _build(tmp_path)
        resolved = {
            d.target
            for display in WikilinkExtractor().extract((tmp_path / "hub.md").read_text())
            if (d := diagnose(graph, display)).reason == "resolved" and d.target != "hub.md"
        }
        assert graph.out_links["hub.md"] == resolved
