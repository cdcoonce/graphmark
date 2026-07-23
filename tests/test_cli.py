"""CLI smoke tests: each subcommand emits valid JSON matching the metric function output.

Uses sys.argv patching + capsys — no subprocess needed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from graphmark.config import VaultConfig, load_config
from graphmark.graph import NormalizeResolver, VaultGraph
from graphmark.metrics import (
    bridges,
    clusters,
    hubs,
    neighborhood,
    orphans,
    pagerank,
    siloed_notes,
    stats,
)
from graphmark.parse import WikilinkExtractor

SIMPLE_CONFIG = Path(__file__).parent / "fixtures" / "simple" / "config.toml"
SIMPLE_VAULT = Path(__file__).parent / "fixtures" / "simple" / "vault"


@pytest.fixture(scope="module")
def simple_graph() -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=SIMPLE_VAULT),
        WikilinkExtractor(),
        NormalizeResolver(),
    )


@pytest.fixture(scope="module")
def simple_config() -> VaultConfig:
    return load_config(SIMPLE_CONFIG)


def _run_cli(argv: list[str], capsys) -> str:
    from graphmark.cli import main

    with patch.object(sys, "argv", argv):
        main()
    return capsys.readouterr().out


class TestStatsCommand:
    def test_emits_valid_json(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "stats"], capsys)
        assert json.loads(out) is not None

    def test_matches_metric_output(self, simple_graph, simple_config, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "stats"], capsys)
        assert json.loads(out) == stats(simple_graph)


class TestOrphansCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "orphans"], capsys)
        assert isinstance(json.loads(out), list)

    def test_matches_metric_output(self, simple_graph, simple_config, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "orphans"], capsys)
        assert json.loads(out) == orphans(simple_graph, simple_config)


class TestHubsCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "hubs"], capsys)
        assert isinstance(json.loads(out), list)

    def test_matches_metric_output(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "hubs"], capsys)
        assert json.loads(out) == hubs(simple_graph)


class TestClustersCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "clusters"], capsys)
        assert isinstance(json.loads(out), list)

    def test_matches_metric_output(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "clusters"], capsys)
        assert json.loads(out) == clusters(simple_graph)


class TestBridgesCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "bridges"], capsys)
        assert isinstance(json.loads(out), list)

    def test_matches_metric_output(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "bridges"], capsys)
        assert json.loads(out) == bridges(simple_graph)


class TestNeighborhoodCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(
            [
                "graphmark",
                "--config",
                str(SIMPLE_CONFIG),
                "neighborhood",
                "--note",
                "brain/hub.md",
            ],
            capsys,
        )
        assert isinstance(json.loads(out), dict)

    def test_matches_metric_output(self, simple_graph, capsys):
        out = _run_cli(
            [
                "graphmark",
                "--config",
                str(SIMPLE_CONFIG),
                "neighborhood",
                "--note",
                "brain/hub.md",
            ],
            capsys,
        )
        assert json.loads(out) == neighborhood(simple_graph, "brain/hub.md", depth=1)

    def test_depth_flag(self, simple_graph, capsys):
        out = _run_cli(
            [
                "graphmark",
                "--config",
                str(SIMPLE_CONFIG),
                "neighborhood",
                "--note",
                "brain/hub.md",
                "--depth",
                "2",
            ],
            capsys,
        )
        assert json.loads(out) == neighborhood(simple_graph, "brain/hub.md", depth=2)

    def test_unknown_note_exits_2_with_stderr_message(self, capsys):
        with patch.object(
            sys,
            "argv",
            [
                "graphmark",
                "--config",
                str(SIMPLE_CONFIG),
                "neighborhood",
                "--note",
                "unknown/note.md",
            ],
        ):
            from graphmark.cli import main

            with pytest.raises(SystemExit) as excinfo:
                main()
        assert excinfo.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "unknown/note.md" in captured.err


class TestPagerankCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "pagerank"], capsys)
        assert isinstance(json.loads(out), list)

    def test_matches_metric_output(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "pagerank"], capsys)
        assert json.loads(out) == pagerank(simple_graph)


class TestExportDotCommand:
    def test_emits_dot_output(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "export", "dot"], capsys)
        assert out.strip().startswith("digraph")

    def test_dot_contains_nodes(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "export", "dot"], capsys)
        for node in simple_graph.nodes:
            assert node in out

    def test_root_flag(self, simple_graph, capsys):
        out = _run_cli(
            ["graphmark", "--root", str(SIMPLE_VAULT), "stats"],
            capsys,
        )
        assert json.loads(out) == stats(simple_graph)


class TestSiloedCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "siloed"], capsys)
        assert isinstance(json.loads(out), list)

    def test_matches_metric_output(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "siloed"], capsys)
        assert json.loads(out) == siloed_notes(simple_graph)
