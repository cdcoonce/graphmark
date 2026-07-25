"""Every CLI example in the README must actually run (#130).

`--config` and `--root` were defined on the parent parser only, so argparse accepted them only
*before* the subcommand. All ten examples in the README's CLI block are written the other way, and
the README is the PyPI landing page — so the first thing a new user copies errored.

It survived because the suite used the working form exclusively (`["graphmark", "--root", X,
"stats"]`), and nothing ever exercised the documented one. That is the actual defect: the docs and
the parser had no shared test. This module closes it by **extracting the commands from README.md**
and running them, so an example that stops working fails the gate rather than shipping to PyPI.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import pytest

from graphmark.cli import main

README = Path(__file__).resolve().parents[1] / "README.md"
FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "simple" / "vault"


def _invoke(argv: list[str], monkeypatch) -> int:
    """Run the CLI with ``argv`` and return its exit code — 0 when ``main`` returns normally.

    Only ``check`` and the error paths call ``sys.exit``; the reporting subcommands fall off the end
    of ``main``, so a bare ``pytest.raises(SystemExit)`` would fail them all.
    """
    monkeypatch.setattr("sys.argv", argv)
    try:
        main()
    except SystemExit as exit_:
        return exit_.code if isinstance(exit_.code, int) else 1
    return 0


def _readme_commands() -> list[str]:
    """Every `graphmark ...` invocation inside a fenced block in the README."""
    # The info string is required and the closing fence must start a line: an optional tag lets the
    # non-greedy match begin at a *closing* fence and swallow prose between blocks, which silently
    # yields zero commands — caught by the guard test below rather than shipping a vacuous suite.
    blocks = re.findall(
        r"^```(?:bash|console|sh)\n(.*?)^```", README.read_text(), re.DOTALL | re.MULTILINE
    )
    commands = []
    for block in blocks:
        for line in block.splitlines():
            line = line.removeprefix("$ ").strip()
            if line.startswith("graphmark "):
                commands.append(line)
    return commands


COMMANDS = _readme_commands()


def test_the_readme_actually_contains_examples():
    # Guards the parametrization: a regex that silently matched nothing would make every test
    # below vacuous and the suite would still be green.
    assert len(COMMANDS) >= 10


@pytest.mark.parametrize("command", COMMANDS, ids=lambda c: c[:40])
def test_every_readme_example_runs(command, tmp_path, capsys, monkeypatch):
    config = tmp_path / "vault.toml"
    config.write_text(f'root = "{FIXTURE_VAULT}"\n\n[check]\nmax_orphans = 0\n', encoding="utf-8")

    argv = shlex.split(command.split(">")[0])  # drop a shell redirect: `export dot > graph.dot`
    argv = [
        str(FIXTURE_VAULT) if a == "/path/to/vault" else str(config) if a == "vault.toml" else a
        for a in argv
    ]
    # The README's neighborhood example names a placeholder note; point it at a real one.
    if "--note" in argv:
        argv[argv.index("--note") + 1] = "brain/hub.md"

    code = _invoke(argv, monkeypatch)
    # `check` is the one example the README shows breaching; everything else must succeed.
    expected = 1 if "check" in argv else 0
    assert code == expected, capsys.readouterr().err


class TestGlobalsAcceptBothPositions:
    def _run(self, argv, capsys, monkeypatch):
        return _invoke(argv, monkeypatch), capsys.readouterr()

    def test_trailing_root_matches_leading_root(self, capsys, monkeypatch):
        leading = self._run(
            ["graphmark", "--root", str(FIXTURE_VAULT), "stats"], capsys, monkeypatch
        )
        trailing = self._run(
            ["graphmark", "stats", "--root", str(FIXTURE_VAULT)], capsys, monkeypatch
        )
        assert leading[0] == trailing[0] == 0
        assert leading[1].out == trailing[1].out

    def test_a_global_given_twice_with_the_same_value_is_fine(self, capsys, monkeypatch):
        code, _ = self._run(
            ["graphmark", "--root", str(FIXTURE_VAULT), "stats", "--root", str(FIXTURE_VAULT)],
            capsys,
            monkeypatch,
        )
        assert code == 0

    def test_a_global_given_twice_with_conflicting_values_is_a_usage_error(
        self, capsys, monkeypatch
    ):
        code, captured = self._run(
            ["graphmark", "--root", str(FIXTURE_VAULT), "stats", "--root", "/elsewhere"],
            capsys,
            monkeypatch,
        )
        assert code == 2
        assert "--root" in captured.err

    def test_two_conflicting_trailing_values_are_a_usage_error(self, capsys, monkeypatch):
        # Both occurrences land on the *same* parser here, where argparse's own last-wins would
        # swallow the first without a word — which is why the options collect with append.
        code, captured = self._run(
            ["graphmark", "stats", "--root", str(FIXTURE_VAULT), "--root", "/elsewhere"],
            capsys,
            monkeypatch,
        )
        assert code == 2
        assert "--root" in captured.err

    def test_two_conflicting_leading_values_are_a_usage_error(self, capsys, monkeypatch):
        code, captured = self._run(
            ["graphmark", "--root", str(FIXTURE_VAULT), "--root", "/elsewhere", "stats"],
            capsys,
            monkeypatch,
        )
        assert code == 2
        assert "--root" in captured.err

    def test_conflicting_config_is_a_usage_error(self, tmp_path, capsys, monkeypatch):
        a = tmp_path / "a.toml"
        a.write_text(f'root = "{FIXTURE_VAULT}"\n', encoding="utf-8")
        code, captured = self._run(
            ["graphmark", "--config", str(a), "stats", "--config", "b.toml"], capsys, monkeypatch
        )
        assert code == 2
        assert "--config" in captured.err

    def test_neither_position_given_is_still_a_usage_error(self, capsys, monkeypatch):
        code, _ = self._run(["graphmark", "stats"], capsys, monkeypatch)
        assert code == 2
