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


def _run_cli_expect_exit(argv: list[str], capsys, code: int):
    """Run the CLI expecting SystemExit(code); return (stdout, stderr)."""
    from graphmark.cli import main

    with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == code
    captured = capsys.readouterr()
    return captured.out, captured.err


class TestUsageErrorConvention:
    """One rule: 0 = success, 2 = usage error. stdout is data only, never help text."""

    def test_no_subcommand_exits_2_with_help_on_stderr(self, capsys):
        from graphmark.cli import main

        with patch.object(sys, "argv", ["graphmark"]), pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        # Piping stdout must never capture help text as if it were data.
        assert captured.out == ""
        assert "usage: graphmark" in captured.err

    def test_missing_config_and_root_exits_2(self, capsys):
        out, err = _run_cli_expect_exit(["graphmark", "stats"], capsys, 2)
        assert out == ""
        assert "--config" in err and "--root" in err

    def test_unknown_flag_exits_2(self, capsys):
        _run_cli_expect_exit(["graphmark", "--nope", "stats"], capsys, 2)

    def test_invalid_subcommand_exits_2(self, capsys):
        _run_cli_expect_exit(["graphmark", "no-such-command"], capsys, 2)

    def test_invalid_export_format_exits_2(self, capsys):
        argv = ["graphmark", "--root", str(SIMPLE_VAULT), "export", "gml"]
        _run_cli_expect_exit(argv, capsys, 2)


class TestVersionAndHelp:
    """A published CLI must be self-documenting and able to report its own version."""

    def test_version_flag_prints_the_package_version_and_exits_0(self, capsys):
        from graphmark import __version__
        from graphmark.cli import main

        with patch.object(sys, "argv", ["graphmark", "--version"]), pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 0
        assert __version__ in capsys.readouterr().out

    def test_main_help_describes_every_subcommand(self, capsys):
        from graphmark.cli import main

        with patch.object(sys, "argv", ["graphmark", "--help"]), pytest.raises(SystemExit):
            main()
        out = capsys.readouterr().out
        # Each subcommand carries a help string, so the command list is not a bare choices dump.
        assert "Articulation points" in out
        assert "degree 0" in out
        assert "Aggregate vault stats" in out

    @pytest.mark.parametrize(
        "command,needle",
        [
            ("hubs", "How many hubs"),
            ("neighborhood", "Vault-relative path"),
            ("pagerank", "Damping factor"),
            ("export", "Output format"),
        ],
    )
    def test_subcommand_help_documents_its_flags(self, command, needle, capsys):
        from graphmark.cli import main

        argv = ["graphmark", command, "--help"]
        with patch.object(sys, "argv", argv), pytest.raises(SystemExit):
            main()
        assert needle in capsys.readouterr().out


class TestBadInputHandling:
    """A bad path or config must fail loudly with exit 2 — never silently-empty JSON."""

    def test_nonexistent_root_exits_2_not_empty_graph(self, tmp_path, capsys):
        missing = tmp_path / "typo-vault"
        out, err = _run_cli_expect_exit(["graphmark", "--root", str(missing), "stats"], capsys, 2)
        assert out == ""  # must NOT print {"notes": 0, ...}
        assert "typo-vault" in err

    def test_nonexistent_config_exits_2(self, tmp_path, capsys):
        missing = tmp_path / "no-such.toml"
        out, err = _run_cli_expect_exit(["graphmark", "--config", str(missing), "stats"], capsys, 2)
        assert out == ""
        assert "no-such.toml" in err

    def test_malformed_toml_exits_2(self, tmp_path, capsys):
        bad = tmp_path / "bad.toml"
        bad.write_text('root = "vault"\nthis is not = = valid toml\n')
        out, err = _run_cli_expect_exit(["graphmark", "--config", str(bad), "stats"], capsys, 2)
        assert out == ""
        assert err.startswith("error:")

    def test_config_missing_root_exits_2(self, tmp_path, capsys):
        rootless = tmp_path / "rootless.toml"
        rootless.write_text('scoped_folders = ["brain"]\n')
        out, err = _run_cli_expect_exit(
            ["graphmark", "--config", str(rootless), "stats"], capsys, 2
        )
        assert out == ""
        assert "root" in err

    def test_rootless_config_works_when_root_is_supplied(self, simple_graph, capsys):
        # The shipped configs/my-brain.toml has no root key; pairing it with --root must work.
        rootless = SIMPLE_CONFIG.parent / "rootless-probe.toml"
        rootless.write_text('excluded_dirs = [".git"]\n')
        try:
            out = _run_cli(
                ["graphmark", "--config", str(rootless), "--root", str(SIMPLE_VAULT), "stats"],
                capsys,
            )
            assert json.loads(out) == stats(simple_graph)
        finally:
            rootless.unlink()

    def test_shipped_reference_config_works_with_root(self, capsys):
        repo_config = Path(__file__).parent.parent / "configs" / "my-brain.toml"
        out = _run_cli(
            ["graphmark", "--config", str(repo_config), "--root", str(SIMPLE_VAULT), "stats"],
            capsys,
        )
        assert json.loads(out)["notes"] >= 0


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

    def test_unknown_note_exits_2_with_stderr_and_no_stdout(self, capsys):
        from graphmark.cli import main

        argv = [
            "graphmark",
            "--config",
            str(SIMPLE_CONFIG),
            "neighborhood",
            "--note",
            "brain/typo.md",
        ]
        with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "brain/typo.md" in captured.err


class TestPagerankCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "pagerank"], capsys)
        assert isinstance(json.loads(out), list)

    def test_matches_metric_output(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "pagerank"], capsys)
        assert json.loads(out) == pagerank(simple_graph)

    def test_bad_alpha_exits_2_with_stderr_and_no_stdout(self, capsys):
        from graphmark.cli import main

        argv = ["graphmark", "--config", str(SIMPLE_CONFIG), "pagerank", "--alpha", "1.5"]
        with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "alpha" in captured.err


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


class TestGapsCommand:
    def test_exits_2_with_stderr_guidance_and_no_stdout(self, capsys):
        from graphmark.cli import main

        argv = ["graphmark", "--config", str(SIMPLE_CONFIG), "gaps"]
        with patch.object(sys, "argv", argv), pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2
        captured = capsys.readouterr()
        assert captured.out == ""  # never silently prints []
        assert "injected similarity source" in captured.err
        assert "graphmark.metrics.gaps" in captured.err


class TestSiloedCommand:
    def test_emits_valid_json(self, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "siloed"], capsys)
        assert isinstance(json.loads(out), list)

    def test_matches_metric_output(self, simple_graph, capsys):
        out = _run_cli(["graphmark", "--config", str(SIMPLE_CONFIG), "siloed"], capsys)
        assert json.loads(out) == siloed_notes(simple_graph)
