"""Tests for config.py: load_config, and config-driven generalization."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from graphmark.config import load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import hubs, orphans
from graphmark.parse import WikilinkExtractor

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SIMPLE_DIR = FIXTURE_DIR / "simple"
SIMPLE_VAULT = SIMPLE_DIR / "vault"
SIMPLE_EXPECTED = json.loads((SIMPLE_DIR / "expected.json").read_text())

ALT_DIR = FIXTURE_DIR / "alt"
ALT_CONFIG_PATH = ALT_DIR / "config.toml"
ALT_EXPECTED = json.loads((ALT_DIR / "expected.json").read_text())

MY_BRAIN_CONFIG = Path(__file__).parent.parent / "configs" / "my-brain.toml"


class TestLoadConfig:
    def test_scoped_folders(self):
        cfg = load_config(MY_BRAIN_CONFIG)
        assert cfg.scoped_folders == [
            "brain",
            "work",
            "personal",
            "org",
            "perf",
            "reference",
            "thinking",
        ]

    def test_excluded_dirs(self):
        cfg = load_config(MY_BRAIN_CONFIG)
        assert cfg.excluded_dirs == [".brain", "templates", ".claude", "session-logs"]

    def test_rules_files(self):
        cfg = load_config(MY_BRAIN_CONFIG)
        assert cfg.rules_files == ["CLAUDE.md", "CLAUDE.local.md"]

    def test_wikilink_pattern(self):
        cfg = load_config(MY_BRAIN_CONFIG)
        assert cfg.wikilink_pattern == r"\[\[(.+?)\]\]"

    def test_orphan_min_chars(self):
        cfg = load_config(MY_BRAIN_CONFIG)
        assert cfg.orphan_min_chars == 300

    def test_transient_prefixes_is_tuple(self):
        cfg = load_config(MY_BRAIN_CONFIG)
        assert isinstance(cfg.transient_prefixes, tuple)
        assert cfg.transient_prefixes == ("personal/tasks/", "work/tasks/")

    def test_root_from_toml_alt_config(self):
        cfg = load_config(ALT_CONFIG_PATH)
        assert cfg.root == ALT_DIR / "vault"


class TestWikilinkPatternWiring:
    """WikilinkExtractor uses the pattern from config, not a hardcoded constant."""

    def test_custom_pattern_is_honored(self):
        extractor = WikilinkExtractor(r"\{\{(.+?)\}\}")
        assert extractor.extract("{{Foo}} [[Bar]]") == ["Foo"]

    def test_default_pattern_matches_config_default(self):
        extractor = WikilinkExtractor()
        assert extractor.extract("[[Foo]]") == ["Foo"]


class TestSimpleFixtureViaLoadConfig:
    """Prove simple fixture still matches oracle when config comes from load_config."""

    @pytest.fixture(scope="class")
    def graph_and_config(self):
        cfg = load_config(MY_BRAIN_CONFIG)
        cfg = replace(cfg, root=SIMPLE_VAULT)
        return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver()), cfg

    def test_orphans_match_oracle(self, graph_and_config):
        graph, cfg = graph_and_config
        result = orphans(graph, cfg)
        assert result == SIMPLE_EXPECTED["orphans"]

    def test_hubs_match_oracle(self, graph_and_config):
        graph, cfg = graph_and_config
        result = hubs(graph)
        assert result == SIMPLE_EXPECTED["hubs"]


class TestAltFixture:
    """Prove config-driven generalization: different folder names work without hardcoding."""

    @pytest.fixture(scope="class")
    def graph_and_config(self):
        cfg = load_config(ALT_CONFIG_PATH)
        return VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver()), cfg

    def test_orphans_match_oracle(self, graph_and_config):
        graph, cfg = graph_and_config
        result = orphans(graph, cfg)
        assert result == ALT_EXPECTED["orphans"]

    def test_hubs_match_oracle(self, graph_and_config):
        graph, cfg = graph_and_config
        result = hubs(graph)
        assert result == ALT_EXPECTED["hubs"]
