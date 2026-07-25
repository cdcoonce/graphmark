"""Frontmatter `aliases:` resolution — a declared alias is a real name for a note.

Obsidian's `aliases:` property is a core feature, not a vault convention, and graphmark claims to
work on any Obsidian-family vault. Until now it never read frontmatter during resolution, so every
link written against an alias was reported broken. Measured on a real 521-note vault: stock
graphmark reported **23 broken links against an actual 0**, and dropped the corresponding edges —
a 100% false-positive rate in `max_unresolved_links`, the flagship `graphmark check` threshold.

The behavioral spec is the reference implementation this replaces (the consumer's `AliasResolver`).
Its six rules, each of which has a test below:

  1. the base resolver runs FIRST — a real note named X always beats an alias X, or renaming a note
     could silently hijack live links. NOTE: rules 3 and 4 make this ordering structurally
     unreachable (no display can match both a catalog key and an alias key), so mutating the order
     leaves this suite green. It is kept as insurance against a future relaxation of those rules,
     and is deliberately not claimed as test-covered;
  2. an alias claimed by two or more notes resolves to nothing — the same refusal graphmark already
     applies to colliding basenames;
  3. an alias colliding with any real note name is dropped ENTIRELY, not merely deprioritized;
  4. a path-qualified display never matches an alias — `[[folder/note]]` is a path, not a name;
  5. alias keys normalize through the same function as note names, so the two cannot drift;
  6. fail-soft — an unreadable or unparseable note yields no aliases, never an exception.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph, diagnose
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, aliases: list[str] | None = None, body: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    front = ""
    if aliases is not None:
        items = "".join(f"  - {a}\n" for a in aliases)
        front = f"---\naliases:\n{items}---\n\n"
    path.write_text(front + body, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestAliasResolution:
    def test_a_link_to_an_alias_resolves_to_the_note(self, tmp_path):
        _write(tmp_path, "notes/2026-04-11-mood-tracker.md", aliases=["Mood Tracker"])
        _write(tmp_path, "src.md", body="See [[Mood Tracker]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["src.md"] == {"notes/2026-04-11-mood-tracker.md"}

    def test_an_alias_link_diagnoses_as_resolved(self, tmp_path):
        _write(tmp_path, "notes/target.md", aliases=["Other Name"])
        _write(tmp_path, "src.md", body="See [[Other Name]].\n")
        d = diagnose(_build(tmp_path), "Other Name")
        assert (d.reason, d.target) == ("resolved", "notes/target.md")

    def test_several_aliases_on_one_note_all_resolve(self, tmp_path):
        _write(tmp_path, "n.md", aliases=["First", "Second", "Third"])
        _write(tmp_path, "src.md", body="[[First]] [[Second]] [[Third]]\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["src.md"] == {"n.md"}

    @pytest.mark.parametrize(
        "display", ["Mood Tracker", "mood tracker", "MOOD TRACKER", "Mood-Tracker"]
    )
    def test_alias_keys_normalize_like_note_names(self, tmp_path, display):
        # Rule 5: same normalization as note names — case, punctuation and whitespace all fold.
        _write(tmp_path, "n.md", aliases=["Mood Tracker"])
        _write(tmp_path, "src.md", body=f"See [[{display}]].\n")
        assert _build(tmp_path).unresolved == {}

    @pytest.mark.parametrize("form", ["Alias Name|shown", "Alias Name#Section", "Alias Name.md"])
    def test_alias_display_forms_resolve(self, tmp_path, form):
        _write(tmp_path, "n.md", aliases=["Alias Name"])
        _write(tmp_path, "src.md", body=f"See [[{form}]].\n")
        assert _build(tmp_path).unresolved == {}

    def test_inline_alias_lists_work_too(self, tmp_path):
        (tmp_path / "n.md").write_text("---\naliases: [One, Two]\n---\n", encoding="utf-8")
        (tmp_path / "src.md").write_text("See [[Two]].\n", encoding="utf-8")
        assert _build(tmp_path).unresolved == {}

    def test_a_scalar_alias_works(self, tmp_path):
        (tmp_path / "n.md").write_text("---\naliases: Solo Name\n---\n", encoding="utf-8")
        (tmp_path / "src.md").write_text("See [[Solo Name]].\n", encoding="utf-8")
        assert _build(tmp_path).unresolved == {}


class TestRealNamesWin:
    """Rule 1 + rule 3 — the anti-hijacking guarantees."""

    def test_a_real_note_beats_an_alias_of_the_same_name(self, tmp_path):
        _write(tmp_path, "real/Target.md")
        _write(tmp_path, "other/impostor.md", aliases=["Target"])
        _write(tmp_path, "src.md", body="See [[Target]].\n")
        graph = _build(tmp_path)
        assert graph.out_links["src.md"] == {"real/Target.md"}

    def test_an_alias_colliding_with_a_real_name_is_dropped_entirely(self, tmp_path):
        # Rule 3: not merely deprioritized. Two notes named "note" make the bare link ambiguous;
        # a third note claiming "note" as an alias must not rescue it into resolving.
        _write(tmp_path, "one/note.md")
        _write(tmp_path, "two/note.md")
        _write(tmp_path, "three/other.md", aliases=["note"])
        _write(tmp_path, "src.md", body="See [[note]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {"src.md": ["note"]}
        assert graph.out_links["src.md"] == set()

    def test_a_notes_own_alias_does_not_shadow_another_notes_title(self, tmp_path):
        _write(tmp_path, "a/Real Title.md")
        _write(tmp_path, "b/other.md", aliases=["Real Title"])
        _write(tmp_path, "src.md", body="See [[Real Title]].\n")
        assert _build(tmp_path).out_links["src.md"] == {"a/Real Title.md"}


class TestAmbiguousAliases:
    """Rule 2 — ambiguity stays ambiguous."""

    def test_an_alias_claimed_by_two_notes_resolves_to_nothing(self, tmp_path):
        _write(tmp_path, "a.md", aliases=["Shared"])
        _write(tmp_path, "b.md", aliases=["Shared"])
        _write(tmp_path, "src.md", body="See [[Shared]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {"src.md": ["Shared"]}
        assert graph.out_links["src.md"] == set()

    def test_an_alias_claimed_twice_by_the_same_note_still_resolves(self, tmp_path):
        # Duplicate within one note is not a conflict — one claimant, one target.
        _write(tmp_path, "a.md", aliases=["Shared", "Shared"])
        _write(tmp_path, "src.md", body="See [[Shared]].\n")
        assert _build(tmp_path).out_links["src.md"] == {"a.md"}

    def test_a_contested_alias_does_not_poison_an_uncontested_one(self, tmp_path):
        _write(tmp_path, "a.md", aliases=["Shared", "Unique A"])
        _write(tmp_path, "b.md", aliases=["Shared"])
        _write(tmp_path, "src.md", body="[[Shared]] and [[Unique A]]\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {"src.md": ["Shared"]}
        assert graph.out_links["src.md"] == {"a.md"}


class TestPathQualifiedLinks:
    """Rule 4 — a path is not a name."""

    def test_a_path_qualified_display_never_matches_an_alias(self, tmp_path):
        _write(tmp_path, "n.md", aliases=["folder/thing"])
        _write(tmp_path, "src.md", body="See [[folder/thing]].\n")
        assert _build(tmp_path).unresolved == {"src.md": ["folder/thing"]}

    def test_a_slash_bearing_alias_is_rejected_at_index_time(self, tmp_path):
        # The lookup-side guard (skip alias lookup for path-qualified displays) is not enough on
        # its own: normalization turns "/" into a space, so an alias "folder/thing" would key as
        # "folder thing" and be reachable from a slash-free display. The reference implementation
        # refuses such an alias when building the map, and so must this.
        _write(tmp_path, "n.md", aliases=["folder/thing"])
        _write(tmp_path, "src.md", body="See [[folder thing]].\n")
        graph = _build(tmp_path)
        assert graph.aliases == {}
        assert graph.unresolved == {"src.md": ["folder thing"]}

    def test_path_resolution_still_works_alongside_aliases(self, tmp_path):
        _write(tmp_path, "docs/deep/note.md", aliases=["Nickname"])
        _write(tmp_path, "src.md", body="[[deep/note]] and [[Nickname]]\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["src.md"] == {"docs/deep/note.md"}


class TestScopeAndFailSoft:
    def test_an_out_of_scope_note_contributes_no_aliases(self, tmp_path):
        # Out-of-scope notes are not part of the graph, so their names — including alias names —
        # cannot become link targets.
        _write(tmp_path, "docs/a.md")
        _write(tmp_path, "templates/t.md", aliases=["Template Nickname"])
        _write(tmp_path, "docs/src.md", body="See [[Template Nickname]].\n")
        graph = _build(tmp_path, scoped_folders=["docs"])
        assert graph.unresolved == {"docs/src.md": ["Template Nickname"]}

    def test_a_note_without_frontmatter_is_fine(self, tmp_path):
        _write(tmp_path, "n.md")
        _write(tmp_path, "src.md", body="See [[Nowhere]].\n")
        assert _build(tmp_path).unresolved == {"src.md": ["Nowhere"]}

    def test_an_empty_alias_list_is_fine(self, tmp_path):
        (tmp_path / "n.md").write_text("---\naliases:\n---\n", encoding="utf-8")
        (tmp_path / "src.md").write_text("See [[Nowhere]].\n", encoding="utf-8")
        assert _build(tmp_path).unresolved == {"src.md": ["Nowhere"]}

    def test_an_empty_alias_entry_is_ignored(self, tmp_path):
        (tmp_path / "n.md").write_text('---\naliases:\n  - ""\n  - Real\n---\n', encoding="utf-8")
        (tmp_path / "src.md").write_text("See [[Real]].\n", encoding="utf-8")
        assert _build(tmp_path).unresolved == {}

    def test_a_non_list_aliases_value_does_not_raise(self, tmp_path):
        # Rule 6: anything unparseable yields no aliases rather than taking the graph down.
        (tmp_path / "n.md").write_text("---\naliases: 42\n---\n", encoding="utf-8")
        (tmp_path / "src.md").write_text("See [[Nowhere]].\n", encoding="utf-8")
        assert _build(tmp_path).unresolved == {"src.md": ["Nowhere"]}

    def test_a_self_alias_link_is_not_an_edge(self, tmp_path):
        _write(tmp_path, "solo.md", aliases=["Me"], body="I link to [[Me]].\n")
        graph = _build(tmp_path)
        assert graph.unresolved == {}
        assert graph.out_links["solo.md"] == set()


class TestAliasesAreInspectable:
    def test_the_graph_exposes_the_resolved_alias_map(self, tmp_path):
        _write(tmp_path, "n.md", aliases=["Nickname"])
        graph = _build(tmp_path)
        assert graph.aliases == {"nickname": "n.md"}

    def test_contested_and_colliding_aliases_are_absent_from_the_map(self, tmp_path):
        _write(tmp_path, "real.md")
        _write(tmp_path, "a.md", aliases=["Shared", "real"])
        _write(tmp_path, "b.md", aliases=["Shared"])
        assert _build(tmp_path).aliases == {}

    def test_directly_constructed_graph_defaults_to_no_aliases(self):
        assert VaultGraph(nodes={}, out_links={}, back_links={}).aliases == {}


class TestConfigKnob:
    def test_aliases_can_be_disabled(self, tmp_path):
        _write(tmp_path, "n.md", aliases=["Nickname"])
        _write(tmp_path, "src.md", body="See [[Nickname]].\n")
        graph = _build(tmp_path, resolve_aliases=False)
        assert graph.unresolved == {"src.md": ["Nickname"]}
        assert graph.aliases == {}

    def test_the_default_is_on(self, tmp_path):
        cfg = VaultConfig(root=tmp_path)
        assert cfg.resolve_aliases is True


class TestFixtureParity:
    def test_no_fixture_note_declares_aliases(self):
        # The parity argument: this change alters what resolves, so it is the most parity-sensitive
        # change since extraction. It is safe only because no frozen fixture uses aliases. Asserted
        # rather than claimed, so it cannot go stale.
        fixtures = Path(__file__).parent / "fixtures"
        offenders = [
            str(n) for n in fixtures.rglob("*.md") if "aliases:" in n.read_text(encoding="utf-8")
        ]
        assert offenders == []
