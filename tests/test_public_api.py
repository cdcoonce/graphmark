"""The top-level package surface: graphmark.build() and the curated re-exports.

Before this, a first-time user needed four submodule imports plus the tribal knowledge that
WikilinkExtractor pairs with NormalizeResolver — a pairing the CLI and the live vault consumer
each re-implemented. The import surface is pinned here so it cannot drift silently.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import graphmark

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "simple"
FIXTURE_VAULT = FIXTURE_DIR / "vault"


class TestBuildHelper:
    def test_builds_from_a_string_path(self):
        graph = graphmark.build(str(FIXTURE_VAULT))
        assert len(graph.nodes) == 6

    def test_builds_from_a_path(self):
        assert graphmark.build(FIXTURE_VAULT).nodes == graphmark.build(str(FIXTURE_VAULT)).nodes

    def test_builds_from_a_vault_config(self):
        config = graphmark.VaultConfig(root=FIXTURE_VAULT)
        assert len(graphmark.build(config).nodes) == 6

    def test_matches_the_explicit_construction_exactly(self):
        explicit = graphmark.VaultGraph.build(
            graphmark.VaultConfig(root=FIXTURE_VAULT),
            graphmark.WikilinkExtractor(),
            graphmark.NormalizeResolver(),
        )
        convenient = graphmark.build(FIXTURE_VAULT)
        assert convenient.nodes.keys() == explicit.nodes.keys()
        assert convenient.out_links == explicit.out_links
        assert convenient.back_links == explicit.back_links
        assert convenient.unresolved == explicit.unresolved

    def test_config_policy_is_honored(self):
        config = graphmark.VaultConfig(root=FIXTURE_VAULT, scoped_folders=["brain"])
        assert all(rel.startswith("brain/") for rel in graphmark.build(config).nodes)

    def test_accepts_custom_extractor_and_resolver(self):
        class NoLinks:
            def extract(self, text: str) -> list[str]:
                return []

        graph = graphmark.build(FIXTURE_VAULT, extractor=NoLinks())
        assert len(graph.nodes) == 6
        assert all(not targets for targets in graph.out_links.values())

    def test_pairs_with_load_config_for_a_toml(self):
        config = graphmark.load_config(FIXTURE_DIR / "config.toml")
        assert len(graphmark.build(config).nodes) == 6

    def test_bad_root_raises(self, tmp_path):
        with pytest.raises(ValueError, match="does not exist"):
            graphmark.build(tmp_path / "nope")


class TestThreeLineQuickstart:
    def test_the_readme_example_works(self):
        graph = graphmark.build(FIXTURE_VAULT)
        assert set(graphmark.stats(graph)) == {
            "notes",
            "edges",
            "orphans",
            "clusters",
            "density",
        }
        assert graphmark.hubs(graph, n=3)


class TestPublicSurface:
    EXPECTED = {
        "__version__",
        "build",
        # config
        "VaultConfig",
        "CheckPolicy",
        "load_config",
        # model + graph
        "Document",
        "VaultGraph",
        "build_catalog",
        "NormalizeResolver",
        "WikilinkExtractor",
        "parse_document",
        # interfaces
        "LinkExtractor",
        "Resolver",
        "Similarity",
        # metrics
        "stats",
        "orphans",
        "hubs",
        "clusters",
        "bridges",
        "siloed_notes",
        "neighborhood",
        "pagerank",
        "gaps",
        "GAPS_DEFAULT_BAND",
        "GAPS_DEFAULT_THRESHOLD",
        "GAPS_DEFAULT_MAX_SCORE",
        "GAPS_DEFAULT_K",
        "GAPS_DEFAULT_HUB_DEGREE",
        # check
        "run_check",
        "unresolved_link_count",
        # link diagnosis
        "diagnose",
        "LinkDiagnosis",
        "DIAGNOSIS_REASONS",
        "candidates_for",
        # dismissal store
        "weaklink_sig",
        "record_dismissal",
        "load_dismissed",
        "active_dismissed_sigs",
        # export
        "to_json",
        "to_dot",
    }

    def test_all_is_exactly_the_curated_surface(self):
        assert set(graphmark.__all__) == self.EXPECTED

    def test_every_exported_name_actually_resolves(self):
        for name in graphmark.__all__:
            assert hasattr(graphmark, name), f"{name} is in __all__ but not importable"

    def test_all_has_no_duplicates(self):
        assert len(graphmark.__all__) == len(set(graphmark.__all__))

    def test_star_import_exposes_the_surface(self):
        namespace: dict = {}
        exec("from graphmark import *", namespace)  # noqa: S102 - pinning the export surface
        for name in graphmark.__all__:
            assert name in namespace
