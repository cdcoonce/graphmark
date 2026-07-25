"""VaultGraph.catalog / .out_of_scope — the resolution state build() used to throw away.

`build` computes two mappings of normalized stem → rel_paths: the in-scope catalog every bare-link
resolution consults (whose multi-entry keys ARE the ambiguity sets), and the out-of-scope mapping
added in #107. Neither survived the call, so a consumer that needs to say anything about a link
beyond "it resolved / it didn't" had to rebuild the entire parse/catalog/resolve stack — which
the-vault's graph_gardener.py does, and which is why four resolution fixes in a row had to be
applied in two places.

This is exposure of existing state, not new behavior: no metric moves, nothing about what resolves
changes. It is the foundation the diagnosis surface stands on.
"""

from __future__ import annotations

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestCatalog:
    def test_maps_normalized_stem_to_rel_path(self, tmp_path):
        _write(tmp_path, "Jordan Ellis.md")
        assert _build(tmp_path).catalog == {"jordan ellis": ["Jordan Ellis.md"]}

    def test_punctuation_normalizes_to_the_same_key_as_spaces(self, tmp_path):
        # The vault's real repair case: [[oura pipeline]] should be able to find oura-pipeline.md.
        _write(tmp_path, "oura-pipeline.md")
        assert _build(tmp_path).catalog == {"oura pipeline": ["oura-pipeline.md"]}

    def test_a_shared_stem_lists_every_colliding_note(self, tmp_path):
        # A key with 2+ paths is exactly what makes a bare link ambiguous — the consumer needs the
        # full collision set to tell a human WHICH notes collided.
        _write(tmp_path, "one/note.md")
        _write(tmp_path, "two/note.md")
        assert _build(tmp_path).catalog["note"] == ["one/note.md", "two/note.md"]

    def test_value_lists_are_sorted_by_rel_path(self, tmp_path):
        # The discriminating case: build walks sorted(rglob) which orders Path objects by their
        # parts tuple, so it yields "a/note.md" before "a-b/note.md" ('a' < 'a-b'). rel_path
        # string order is the opposite ('-' 0x2d < '/' 0x2f). The contract is the string order —
        # these are strings in a byte-stable report — so walk order alone must not satisfy it.
        for rel in ("a/note.md", "a-b/note.md"):
            _write(tmp_path, rel)
        assert _build(tmp_path).catalog["note"] == ["a-b/note.md", "a/note.md"]

    def test_multi_way_collisions_are_fully_ordered(self, tmp_path):
        for rel in ("zeta/note.md", "alpha/note.md", "mid/note.md"):
            _write(tmp_path, rel)
        assert _build(tmp_path).catalog["note"] == ["alpha/note.md", "mid/note.md", "zeta/note.md"]

    def test_excludes_everything_build_filtered_out(self, tmp_path):
        _write(tmp_path, "docs/keep.md")
        _write(tmp_path, "templates/skip.md")
        _write(tmp_path, "CLAUDE.md")
        graph = _build(tmp_path, scoped_folders=["docs"], rules_files=["CLAUDE.md"])
        assert graph.catalog == {"keep": ["docs/keep.md"]}

    def test_covers_every_node(self, tmp_path):
        _write(tmp_path, "a.md")
        _write(tmp_path, "b/c.md")
        graph = _build(tmp_path)
        assert sorted(p for paths in graph.catalog.values() for p in paths) == sorted(graph.nodes)

    def test_empty_vault_has_an_empty_catalog(self, tmp_path):
        vault = tmp_path / "empty"
        vault.mkdir()
        assert _build(vault).catalog == {}


class TestOutOfScope:
    def test_rules_file_appears(self, tmp_path):
        _write(tmp_path, "notes/a.md")
        _write(tmp_path, "CLAUDE.md")
        graph = _build(tmp_path, rules_files=["CLAUDE.md"])
        assert graph.out_of_scope == {"claude": ["CLAUDE.md"]}

    def test_unscoped_folder_appears(self, tmp_path):
        _write(tmp_path, "docs/a.md")
        _write(tmp_path, "templates/Intake Guide.md")
        graph = _build(tmp_path, scoped_folders=["docs"])
        assert graph.out_of_scope == {"intake guide": ["templates/Intake Guide.md"]}

    def test_excluded_dir_appears(self, tmp_path):
        _write(tmp_path, "a.md")
        _write(tmp_path, "archive/old thing.md")
        graph = _build(tmp_path, excluded_dirs=["archive"])
        assert graph.out_of_scope == {"old thing": ["archive/old thing.md"]}

    def test_value_lists_are_sorted_by_rel_path(self, tmp_path):
        # Same discriminating case as the catalog: walk order would yield "t/a/shared.md" first.
        _write(tmp_path, "docs/a.md")
        for rel in ("t/a/shared.md", "t/a-b/shared.md"):
            _write(tmp_path, rel)
        graph = _build(tmp_path, scoped_folders=["docs"])
        assert graph.out_of_scope["shared"] == ["t/a-b/shared.md", "t/a/shared.md"]

    def test_paths_use_posix_separators(self, tmp_path):
        # rel_paths are compared against link text and printed into reports, so they must not
        # change shape on Windows.
        _write(tmp_path, "docs/a.md")
        _write(tmp_path, "templates/nested/guide.md")
        graph = _build(tmp_path, scoped_folders=["docs"])
        assert graph.out_of_scope["guide"] == ["templates/nested/guide.md"]

    def test_is_disjoint_from_the_catalog(self, tmp_path):
        _write(tmp_path, "docs/guide.md")
        _write(tmp_path, "templates/guide.md")
        graph = _build(tmp_path, scoped_folders=["docs"])
        assert graph.catalog["guide"] == ["docs/guide.md"]
        assert graph.out_of_scope["guide"] == ["templates/guide.md"]
        assert set(p for ps in graph.catalog.values() for p in ps).isdisjoint(
            p for ps in graph.out_of_scope.values() for p in ps
        )

    def test_a_fully_scoped_vault_has_nothing_out_of_scope(self, tmp_path):
        _write(tmp_path, "a.md")
        _write(tmp_path, "b.md")
        assert _build(tmp_path).out_of_scope == {}


class TestConstruction:
    def test_three_positional_arguments_still_construct(self):
        # Back-compatible: existing consumers and tests build a VaultGraph directly.
        graph = VaultGraph(nodes={}, out_links={}, back_links={})
        assert graph.catalog == {}
        assert graph.out_of_scope == {}

    def test_both_mappings_are_accepted_explicitly(self):
        graph = VaultGraph(
            nodes={},
            out_links={},
            back_links={},
            catalog={"a": ["a.md"]},
            out_of_scope={"b": ["skip/b.md"]},
        )
        assert graph.catalog == {"a": ["a.md"]}
        assert graph.out_of_scope == {"b": ["skip/b.md"]}
