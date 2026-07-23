"""Tests for config.py: load_config unit tests and config-driven oracle assertions.

Path B — simple fixture via load_config reproduces simple/expected.json exactly.
Path A — alt fixture via load_config reproduces alt/expected.json exactly, including the
         transient_prefixes divergence that proves config is actually consulted.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from graphmark.config import VaultConfig, load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import bridges, clusters, hubs, neighborhood, orphans, stats
from graphmark.parse import WikilinkExtractor

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SIMPLE_DIR = FIXTURE_DIR / "simple"
ALT_DIR = FIXTURE_DIR / "alt"
SIMPLE_EXPECTED = json.loads((SIMPLE_DIR / "expected.json").read_text())
ALT_EXPECTED = json.loads((ALT_DIR / "expected.json").read_text())


# ---------------------------------------------------------------------------
# load_config unit tests
# ---------------------------------------------------------------------------


class TestLoadConfig:
    def test_root_resolves_relative_to_toml_dir(self):
        cfg = load_config(SIMPLE_DIR / "config.toml")
        assert cfg.root == SIMPLE_DIR / "vault"

    def test_alt_root_resolves_relative_to_toml_dir(self):
        cfg = load_config(ALT_DIR / "config.toml")
        assert cfg.root == ALT_DIR / "vault"

    def test_missing_optional_key_falls_back_to_dataclass_default(self, tmp_path):
        toml = tmp_path / "minimal.toml"
        toml.write_text('root = "vault"\n')
        cfg = load_config(toml)
        default = VaultConfig(root=tmp_path / "vault")
        assert cfg.scoped_folders == default.scoped_folders
        assert cfg.excluded_dirs == default.excluded_dirs
        assert cfg.rules_files == default.rules_files
        assert cfg.wikilink_pattern == default.wikilink_pattern
        assert cfg.orphan_min_chars == default.orphan_min_chars
        assert cfg.transient_prefixes == default.transient_prefixes

    def test_missing_root_key_raises_value_error(self, tmp_path):
        toml = tmp_path / "no-root.toml"
        toml.write_text('scoped_folders = ["notes"]\n')
        with pytest.raises(ValueError, match=rf"{toml}.*root"):
            load_config(toml)

    def test_transient_prefixes_loaded_as_tuple(self):
        cfg = load_config(ALT_DIR / "config.toml")
        assert isinstance(cfg.transient_prefixes, tuple)
        assert cfg.transient_prefixes == ("daily/",)

    def test_excluded_dirs_loaded(self):
        cfg = load_config(ALT_DIR / "config.toml")
        assert cfg.excluded_dirs == [".git"]


# ---------------------------------------------------------------------------
# Path B — simple fixture via load_config
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def simple_graph_and_config() -> tuple[VaultGraph, VaultConfig]:
    cfg = load_config(SIMPLE_DIR / "config.toml")
    graph = VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())
    return graph, cfg


class TestSimpleFixtureViaLoadConfig:
    """load_config path == direct-construct path: same oracle, same result."""

    def test_stats(self, simple_graph_and_config):
        graph, _ = simple_graph_and_config
        assert stats(graph) == SIMPLE_EXPECTED["stats"]

    def test_orphans(self, simple_graph_and_config):
        graph, cfg = simple_graph_and_config
        assert orphans(graph, cfg) == SIMPLE_EXPECTED["orphans"]

    def test_hubs(self, simple_graph_and_config):
        graph, _ = simple_graph_and_config
        assert hubs(graph) == SIMPLE_EXPECTED["hubs"]

    def test_clusters(self, simple_graph_and_config):
        graph, _ = simple_graph_and_config
        assert clusters(graph) == SIMPLE_EXPECTED["clusters"]

    def test_bridges(self, simple_graph_and_config):
        graph, _ = simple_graph_and_config
        assert bridges(graph) == SIMPLE_EXPECTED["bridges"]

    def test_neighborhood(self, simple_graph_and_config):
        graph, _ = simple_graph_and_config
        for case in SIMPLE_EXPECTED["neighborhood"]:
            result = neighborhood(graph, **case["args"])
            assert result == case["expected"]


# ---------------------------------------------------------------------------
# Path A — alt fixture via load_config (foreign vault, proves generalization)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def alt_graph_and_config() -> tuple[VaultGraph, VaultConfig]:
    cfg = load_config(ALT_DIR / "config.toml")
    graph = VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())
    return graph, cfg


class TestAltFixtureViaLoadConfig:
    """Alt vault: different topology + folder names, proves no my-brain hardcoding."""

    def test_stats(self, alt_graph_and_config):
        graph, _ = alt_graph_and_config
        assert stats(graph) == ALT_EXPECTED["stats"]

    def test_orphans(self, alt_graph_and_config):
        graph, cfg = alt_graph_and_config
        assert orphans(graph, cfg) == ALT_EXPECTED["orphans"]

    def test_transient_prefix_divergence(self, alt_graph_and_config):
        """stats.orphans counts daily/ note; orphan list excludes it — proves config consulted."""
        graph, cfg = alt_graph_and_config
        raw_count = stats(graph)["orphans"]
        orphan_list = orphans(graph, cfg)
        assert raw_count == 3
        assert len(orphan_list) == 2
        assert "daily/2026-07-01.md" not in orphan_list

    def test_hubs(self, alt_graph_and_config):
        graph, _ = alt_graph_and_config
        assert hubs(graph) == ALT_EXPECTED["hubs"]

    def test_clusters(self, alt_graph_and_config):
        graph, _ = alt_graph_and_config
        assert clusters(graph) == ALT_EXPECTED["clusters"]

    def test_bridges(self, alt_graph_and_config):
        graph, _ = alt_graph_and_config
        assert bridges(graph) == ALT_EXPECTED["bridges"]

    def test_neighborhood(self, alt_graph_and_config):
        graph, _ = alt_graph_and_config
        for case in ALT_EXPECTED["neighborhood"]:
            result = neighborhood(graph, **case["args"])
            assert result == case["expected"]
