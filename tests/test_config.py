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
        assert cfg.transient_prefixes == default.transient_prefixes

    def test_missing_root_raises_valueerror_with_path_and_key(self, tmp_path):
        toml = tmp_path / "no-root.toml"
        toml.write_text('scoped_folders = ["a"]\n')
        with pytest.raises(ValueError) as exc:
            load_config(toml)
        msg = str(exc.value)
        assert str(toml) in msg
        assert "root" in msg

    def test_removed_noop_knobs_are_gone(self):
        # wikilink_pattern and orphan_min_chars were silent no-ops; they no longer exist.
        cfg = load_config(SIMPLE_DIR / "config.toml")
        assert not hasattr(cfg, "wikilink_pattern")
        assert not hasattr(cfg, "orphan_min_chars")

    def test_unknown_keys_in_toml_are_ignored(self, tmp_path):
        toml = tmp_path / "extra.toml"
        toml.write_text('root = "vault"\nwikilink_pattern = "x"\norphan_min_chars = 99\n')
        cfg = load_config(toml)  # unknown keys are silently ignored, not an error
        assert cfg.root == tmp_path / "vault"

    def test_root_override_replaces_the_toml_root(self, tmp_path):
        toml = tmp_path / "with-root.toml"
        toml.write_text('root = "vault"\nexcluded_dirs = [".git"]\n')
        cfg = load_config(toml, root_override=tmp_path / "elsewhere")
        assert cfg.root == tmp_path / "elsewhere"
        assert cfg.excluded_dirs == [".git"]  # other keys still honored

    def test_root_override_makes_the_root_key_optional(self, tmp_path):
        # The shipped reference config (configs/my-brain.toml) has no root key — it is meant to
        # be paired with an explicit root, so an override must satisfy the requirement.
        toml = tmp_path / "rootless.toml"
        toml.write_text('scoped_folders = ["brain"]\n')
        cfg = load_config(toml, root_override=tmp_path / "vault")
        assert cfg.root == tmp_path / "vault"
        assert cfg.scoped_folders == ["brain"]

    def test_accepts_a_string_path(self):
        # build() takes str; load_config must too, or the documented pairing is a landmine.
        cfg = load_config(str(SIMPLE_DIR / "config.toml"))
        assert cfg.root == SIMPLE_DIR / "vault"

    def test_accepts_a_string_root_override(self, tmp_path):
        cfg = load_config(str(SIMPLE_DIR / "config.toml"), root_override=str(tmp_path))
        assert cfg.root == tmp_path

    def test_vault_config_coerces_a_string_root_to_path(self):
        cfg = VaultConfig(root=str(SIMPLE_DIR / "vault"))
        assert isinstance(cfg.root, Path)
        assert cfg.root == SIMPLE_DIR / "vault"

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
