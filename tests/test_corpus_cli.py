"""Tests for scripts/corpus/cli.py: the fetch/report/diff subcommands and the offline
cache-miss skip.

No network access anywhere here. ``fetch`` tests build real local git repositories under
``tmp_path`` and use them as "remotes" (same technique as ``tests/test_corpus_fetch.py``).
``report``/``diff`` tests place a synthetic vault directly into a ``tmp_path`` cache directory
(same technique as ``tests/test_corpus_report.py``) alongside a hand-authored expected JSON file
(same technique as ``tests/test_corpus_diff.py``).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.corpus import cli  # noqa: E402
from scripts.corpus.manifest import CorpusVault  # noqa: E402
from scripts.corpus.report import build_vault_report, report_json  # noqa: E402

_SHA = "0123456789abcdef0123456789abcdef01234567"


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _write_manifest(path: Path, vaults: list[dict]) -> None:
    """Write a manifest TOML, same shape as tests/test_corpus_manifest.py's fixture."""
    chunks = []
    for v in vaults:
        chunks.append(
            "[[vault]]\n"
            f"name = {json.dumps(v['name'])}\n"
            f"clone_url = {json.dumps(v.get('clone_url', 'https://github.com/example/vault'))}\n"
            f"sha = {json.dumps(v.get('sha', _SHA))}\n"
            f"license = {json.dumps(v.get('license', 'MIT'))}\n"
            f"excluded_dirs = {json.dumps(v.get('excluded_dirs', []))}\n"
        )
    path.write_text("\n".join(chunks))


def _write_synthetic_vault(cache_root: Path, name: str) -> CorpusVault:
    """Same synthetic vault content as tests/test_corpus_report.py's helper."""
    vault_dir = cache_root / name
    vault_dir.mkdir(parents=True)
    (vault_dir / "alpha.md").write_text("See [[beta]] and [[missing]].\n")
    (vault_dir / "beta.md").write_text("# Beta\n")

    return CorpusVault(
        name=name,
        clone_url="https://github.com/example/vault",
        sha=_SHA,
        license="MIT",
        excluded_dirs=(),
    )


def _make_remote(tmp_path: Path, dirname: str) -> tuple[Path, str]:
    """A two-commit local git repository standing in for an upstream vault, plus its HEAD sha.

    Same technique as tests/test_corpus_fetch.py's ``remote``/``first_sha`` fixtures.
    """
    repo = tmp_path / dirname
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], repo)
    _git(["config", "user.email", "corpus@example.test"], repo)
    _git(["config", "user.name", "corpus test"], repo)

    (repo / "note.md").write_text("# first\n", encoding="utf-8")
    _git(["add", "note.md"], repo)
    _git(["commit", "-q", "-m", "first"], repo)

    sha = _git(["rev-parse", "HEAD"], repo)
    return repo, sha


# --- diff -------------------------------------------------------------------------------------


def test_diff_empty_cache_skips_every_vault_and_exits_0(tmp_path, capsys):
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(
        manifest_path,
        [{"name": "vault-a"}, {"name": "vault-b"}],
    )
    cache_root = tmp_path / "cache"
    expected_dir = tmp_path / "expected"

    code = cli.main(
        [
            "diff",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
            "--expected-dir",
            str(expected_dir),
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "skip vault-a: not fetched" in captured.err
    assert "skip vault-b: not fetched" in captured.err
    assert captured.out == ""


def test_diff_matching_cached_vault_exits_0_with_no_diff_output(tmp_path, capsys):
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path, [{"name": "synthetic-vault"}])
    cache_root = tmp_path / "cache"
    vault = _write_synthetic_vault(cache_root, "synthetic-vault")
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    actual = build_vault_report(vault, cache_root)
    (expected_dir / "synthetic-vault.json").write_text(json.dumps(actual))

    code = cli.main(
        [
            "diff",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
            "--expected-dir",
            str(expected_dir),
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert captured.out == ""


def test_diff_mismatched_cached_vault_exits_1_and_prints_diff(tmp_path, capsys):
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path, [{"name": "synthetic-vault"}])
    cache_root = tmp_path / "cache"
    vault = _write_synthetic_vault(cache_root, "synthetic-vault")
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    actual = build_vault_report(vault, cache_root)
    stale = dict(actual)
    stale["notes"] = actual["notes"] + 1
    (expected_dir / "synthetic-vault.json").write_text(json.dumps(stale))

    code = cli.main(
        [
            "diff",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
            "--expected-dir",
            str(expected_dir),
        ]
    )

    captured = capsys.readouterr()
    assert code == 1
    expected_line = f"synthetic-vault · notes · {stale['notes']} → {actual['notes']}"
    assert expected_line in captured.out


def test_diff_unreadable_manifest_exits_2(tmp_path, capsys):
    manifest_path = tmp_path / "does-not-exist.toml"
    cache_root = tmp_path / "cache"
    expected_dir = tmp_path / "expected"

    code = cli.main(
        [
            "diff",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
            "--expected-dir",
            str(expected_dir),
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")


def test_diff_expected_missing_top_level_field_exits_2(tmp_path, capsys):
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path, [{"name": "synthetic-vault"}])
    cache_root = tmp_path / "cache"
    vault = _write_synthetic_vault(cache_root, "synthetic-vault")
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    actual = build_vault_report(vault, cache_root)
    incomplete = dict(actual)
    del incomplete["links"]
    (expected_dir / "synthetic-vault.json").write_text(json.dumps(incomplete))

    code = cli.main(
        [
            "diff",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
            "--expected-dir",
            str(expected_dir),
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")


def test_diff_malformed_expected_file_exits_2(tmp_path, capsys):
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path, [{"name": "synthetic-vault"}])
    cache_root = tmp_path / "cache"
    _write_synthetic_vault(cache_root, "synthetic-vault")
    expected_dir = tmp_path / "expected"
    expected_dir.mkdir()
    (expected_dir / "synthetic-vault.json").write_text("{not valid json")

    code = cli.main(
        [
            "diff",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
            "--expected-dir",
            str(expected_dir),
        ]
    )

    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.startswith("error:")


# --- fetch --------------------------------------------------------------------------------------


def test_fetch_calls_fetch_vault_for_every_manifest_entry(tmp_path):
    remote_a, sha_a = _make_remote(tmp_path, "remote-a")
    remote_b, sha_b = _make_remote(tmp_path, "remote-b")
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(
        manifest_path,
        [
            {"name": "vault-a", "clone_url": str(remote_a), "sha": sha_a},
            {"name": "vault-b", "clone_url": str(remote_b), "sha": sha_b},
        ],
    )
    cache_root = tmp_path / "cache"

    code = cli.main(
        [
            "fetch",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
        ]
    )

    assert code == 0
    target_a = cache_root / "vault-a"
    target_b = cache_root / "vault-b"
    assert _git(["rev-parse", "HEAD"], target_a) == sha_a
    assert _git(["rev-parse", "HEAD"], target_b) == sha_b
    assert (target_a / "note.md").read_text(encoding="utf-8") == "# first\n"
    assert (target_b / "note.md").read_text(encoding="utf-8") == "# first\n"


# --- report -------------------------------------------------------------------------------------


def test_report_empty_cache_skips_every_vault_and_writes_nothing(tmp_path, capsys):
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path, [{"name": "vault-a"}, {"name": "vault-b"}])
    cache_root = tmp_path / "cache"
    out_dir = tmp_path / "out"

    code = cli.main(
        [
            "report",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
            "--out-dir",
            str(out_dir),
        ]
    )

    captured = capsys.readouterr()
    assert code == 0
    assert "skip vault-a: not fetched" in captured.err
    assert "skip vault-b: not fetched" in captured.err
    assert not out_dir.exists()


def test_report_writes_report_json_for_cached_vault(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    _write_manifest(manifest_path, [{"name": "synthetic-vault"}])
    cache_root = tmp_path / "cache"
    vault = _write_synthetic_vault(cache_root, "synthetic-vault")
    out_dir = tmp_path / "out" / "nested"

    code = cli.main(
        [
            "report",
            "--manifest",
            str(manifest_path),
            "--cache-root",
            str(cache_root),
            "--out-dir",
            str(out_dir),
        ]
    )

    assert code == 0
    written = (out_dir / "synthetic-vault.json").read_text()
    assert written == report_json(vault, cache_root)
