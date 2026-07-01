"""Tests for graph.py: build_catalog, NormalizeResolver, VaultGraph."""

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph, build_catalog
from graphmark.model import Document
from graphmark.parse import WikilinkExtractor

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "simple" / "vault"


def _doc(rel_path: str, text: str = "") -> Document:
    return Document(rel_path=rel_path, text=text, frontmatter={})


class TestBuildCatalog:
    def test_maps_stem_to_rel_path(self):
        docs = [_doc("brain/alpha.md"), _doc("personal/beta.md")]
        catalog = build_catalog(docs)
        assert catalog["alpha"] == ["brain/alpha.md"]
        assert catalog["beta"] == ["personal/beta.md"]

    def test_collision_when_same_stem(self):
        docs = [_doc("dir1/note.md"), _doc("dir2/note.md")]
        catalog = build_catalog(docs)
        assert len(catalog["note"]) == 2

    def test_normalizes_uppercase_stem(self):
        docs = [_doc("brain/MyNote.md")]
        catalog = build_catalog(docs)
        assert "mynote" in catalog

    def test_normalizes_hyphenated_stem(self):
        docs = [_doc("brain/does-not-exist.md")]
        catalog = build_catalog(docs)
        assert "does not exist" in catalog


class TestNormalizeResolver:
    def setup_method(self):
        self.resolver = NormalizeResolver()

    def _catalog(self, *rel_paths: str) -> dict[str, list[str]]:
        return build_catalog([_doc(p) for p in rel_paths])

    def test_resolves_bare_link(self):
        catalog = self._catalog("brain/alpha.md")
        assert self.resolver.resolve("alpha", catalog) == "brain/alpha.md"

    def test_resolves_case_insensitive(self):
        catalog = self._catalog("brain/alpha.md")
        assert self.resolver.resolve("Alpha", catalog) == "brain/alpha.md"

    def test_strips_alias(self):
        catalog = self._catalog("brain/alpha.md")
        assert self.resolver.resolve("Alpha|the first note", catalog) == "brain/alpha.md"

    def test_strips_anchor(self):
        catalog = self._catalog("brain/alpha.md")
        assert self.resolver.resolve("alpha#Section", catalog) == "brain/alpha.md"

    def test_ambiguous_returns_none(self):
        catalog = {"note": ["dir1/note.md", "dir2/note.md"]}
        assert self.resolver.resolve("note", catalog) is None

    def test_unknown_returns_none(self):
        catalog = self._catalog("brain/alpha.md")
        assert self.resolver.resolve("does-not-exist", catalog) is None

    def test_path_suffix_resolution(self):
        catalog = self._catalog("brain/alpha.md", "personal/beta.md")
        assert self.resolver.resolve("brain/alpha", catalog) == "brain/alpha.md"

    def test_path_suffix_unique_despite_ambiguous_stem(self):
        # stem "alpha" is ambiguous, but the full path suffix uniquely identifies the target
        catalog = {"alpha": ["dir1/alpha.md", "dir2/alpha.md"]}
        assert self.resolver.resolve("dir1/alpha", catalog) == "dir1/alpha.md"

    def test_path_suffix_unmatched_returns_none(self):
        catalog = self._catalog("brain/alpha.md")
        assert self.resolver.resolve("other/alpha", catalog) is None


class TestVaultGraphBuild:
    def _build(self) -> VaultGraph:
        return VaultGraph.build(
            VaultConfig(root=FIXTURE_VAULT),
            WikilinkExtractor(),
            NormalizeResolver(),
        )

    def test_nodes_contains_all_six_vault_notes(self):
        vg = self._build()
        assert len(vg.nodes) == 6
        assert "brain/hub.md" in vg.nodes
        assert "reference/island.md" in vg.nodes

    def test_five_resolved_edges_total(self):
        vg = self._build()
        total = sum(len(targets) for targets in vg.out_links.values())
        assert total == 5

    def test_alias_link_produces_no_duplicate_edge(self):
        vg = self._build()
        # hub links [[alpha]] and [[Alpha|the first note]] — must collapse to one edge
        hub_out = vg.out_links.get("brain/hub.md", set())
        assert "brain/alpha.md" in hub_out
        assert len(hub_out) == 3  # alpha, beta, gamma only

    def test_unresolvable_link_forms_no_edge(self):
        vg = self._build()
        # stub.md links to [[does-not-exist]] which cannot be resolved
        assert len(vg.out_links.get("reference/stub.md", set())) == 0

    def test_back_links_inverted_correctly(self):
        vg = self._build()
        assert vg.back_links.get("personal/beta.md") == {"brain/alpha.md", "brain/hub.md"}

    def test_undirected_degrees_match_oracle(self):
        vg = self._build()

        def degree(path: str) -> int:
            return len(vg.out_links.get(path, set()) | vg.back_links.get(path, set()))

        assert degree("brain/hub.md") == 3
        assert degree("personal/beta.md") == 3
        assert degree("brain/alpha.md") == 2
        assert degree("personal/gamma.md") == 2
        assert degree("reference/island.md") == 0
        assert degree("reference/stub.md") == 0
