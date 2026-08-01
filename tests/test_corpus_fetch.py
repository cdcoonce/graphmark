"""Tests for scripts/corpus/fetch.py: idempotent population of the gitignored corpus cache.

No network access anywhere here — every test builds a real git repository under ``tmp_path`` with
``git init`` + commits and uses its actual commit SHAs as the pinned ``CorpusVault.sha``. The
"remote" is a local path, so ``git clone``/``git fetch`` never leave the filesystem.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.corpus.fetch import fetch_vault  # noqa: E402
from scripts.corpus.manifest import CorpusVault  # noqa: E402


def _git(args: list[str], cwd: Path) -> str:
    """Run one git command under ``cwd`` and return its stdout, failing loudly on error."""
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    """A two-commit local git repository standing in for the upstream vault."""
    repo = tmp_path / "remote"
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], repo)
    _git(["config", "user.email", "corpus@example.test"], repo)
    _git(["config", "user.name", "corpus test"], repo)

    (repo / "note.md").write_text("# first\n", encoding="utf-8")
    _git(["add", "note.md"], repo)
    _git(["commit", "-q", "-m", "first"], repo)

    (repo / "note.md").write_text("# second\n", encoding="utf-8")
    _git(["add", "note.md"], repo)
    _git(["commit", "-q", "-m", "second"], repo)
    return repo


@pytest.fixture
def first_sha(remote: Path) -> str:
    return _git(["rev-parse", "HEAD~1"], remote)


@pytest.fixture
def second_sha(remote: Path) -> str:
    return _git(["rev-parse", "HEAD"], remote)


def _vault(remote: Path, sha: str) -> CorpusVault:
    return CorpusVault(
        name="example-vault",
        clone_url=str(remote),
        sha=sha,
        license="MIT",
        excluded_dirs=(".git", ".obsidian"),
    )


class TestFreshClone:
    def test_clones_and_checks_out_the_pinned_sha(self, tmp_path, remote, first_sha):
        cache_root = tmp_path / "cache"
        fetch_vault(_vault(remote, first_sha), cache_root)

        target = cache_root / "example-vault"
        assert _git(["rev-parse", "HEAD"], target) == first_sha
        assert (target / "note.md").read_text(encoding="utf-8") == "# first\n"

    def test_pins_to_head_when_that_is_the_requested_sha(self, tmp_path, remote, second_sha):
        cache_root = tmp_path / "cache"
        fetch_vault(_vault(remote, second_sha), cache_root)

        target = cache_root / "example-vault"
        assert _git(["rev-parse", "HEAD"], target) == second_sha
        assert (target / "note.md").read_text(encoding="utf-8") == "# second\n"


class TestAlreadyCorrect:
    def test_second_call_runs_no_git_network_operation(
        self, tmp_path, monkeypatch, remote, first_sha
    ):
        """A cache entry already at the pinned SHA is left alone: no clone, no fetch, no checkout.

        The spy delegates to the real ``subprocess.run`` (the short-circuit check itself needs
        ``git rev-parse HEAD``) and records every argv, so the assertion below proves the *only*
        git invocation was the local HEAD read — network operations are impossible, not merely
        unobserved.
        """
        cache_root = tmp_path / "cache"
        vault = _vault(remote, first_sha)
        fetch_vault(vault, cache_root)

        target = cache_root / "example-vault"
        sentinel = target / "untracked.md"
        sentinel.write_text("do not touch\n", encoding="utf-8")

        calls: list[list[str]] = []
        real_run = subprocess.run

        def spy(args, *rest, **kwargs):
            calls.append(list(args))
            return real_run(args, *rest, **kwargs)

        monkeypatch.setattr("scripts.corpus.fetch.subprocess.run", spy)
        fetch_vault(vault, cache_root)

        assert calls == [["git", "rev-parse", "HEAD"]]
        assert _git(["rev-parse", "HEAD"], target) == first_sha
        assert (target / "note.md").read_text(encoding="utf-8") == "# first\n"
        assert sentinel.read_text(encoding="utf-8") == "do not touch\n"


class TestWrongSha:
    def test_cache_entry_at_the_wrong_commit_is_corrected(
        self, tmp_path, remote, first_sha, second_sha
    ):
        cache_root = tmp_path / "cache"
        fetch_vault(_vault(remote, second_sha), cache_root)

        target = cache_root / "example-vault"
        assert _git(["rev-parse", "HEAD"], target) == second_sha

        fetch_vault(_vault(remote, first_sha), cache_root)

        assert _git(["rev-parse", "HEAD"], target) == first_sha
        assert (target / "note.md").read_text(encoding="utf-8") == "# first\n"

    def test_commit_added_upstream_after_the_clone_is_fetched(self, tmp_path, remote, first_sha):
        """The pinned SHA may not exist locally yet — the fetch, not the clone, must supply it."""
        cache_root = tmp_path / "cache"
        fetch_vault(_vault(remote, first_sha), cache_root)

        (remote / "note.md").write_text("# third\n", encoding="utf-8")
        _git(["add", "note.md"], remote)
        _git(["commit", "-q", "-m", "third"], remote)
        third_sha = _git(["rev-parse", "HEAD"], remote)

        fetch_vault(_vault(remote, third_sha), cache_root)

        target = cache_root / "example-vault"
        assert _git(["rev-parse", "HEAD"], target) == third_sha
        assert (target / "note.md").read_text(encoding="utf-8") == "# third\n"


class TestShallowFetchFallback:
    def test_falls_back_to_a_full_by_sha_fetch(self, tmp_path, monkeypatch, remote, first_sha):
        """A remote that refuses ``--depth 1 <sha>`` must still land on the pinned commit.

        A local-path remote happily serves the shallow by-SHA form, so the fallback would never
        run under test on its own; forcing that one argv to fail is the only way to exercise it
        without a network remote configured to reject SHA-in-want.
        """
        cache_root = tmp_path / "cache"
        fetch_vault(_vault(remote, first_sha), cache_root)

        (remote / "note.md").write_text("# third\n", encoding="utf-8")
        _git(["add", "note.md"], remote)
        _git(["commit", "-q", "-m", "third"], remote)
        third_sha = _git(["rev-parse", "HEAD"], remote)

        calls: list[list[str]] = []
        real_run = subprocess.run

        def spy(args, *rest, **kwargs):
            calls.append(list(args))
            if "--depth" in args:
                return subprocess.CompletedProcess(args, 1, stdout="", stderr="denied\n")
            return real_run(args, *rest, **kwargs)

        monkeypatch.setattr("scripts.corpus.fetch.subprocess.run", spy)
        fetch_vault(_vault(remote, third_sha), cache_root)

        assert ["git", "fetch", "origin", third_sha] in calls
        target = cache_root / "example-vault"
        assert _git(["rev-parse", "HEAD"], target) == third_sha
        assert (target / "note.md").read_text(encoding="utf-8") == "# third\n"


class TestGitignore:
    def test_corpus_cache_is_gitignored(self):
        entries = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert ".corpus-cache/" in entries
