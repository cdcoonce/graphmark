"""Corpus fetch — populate a local, gitignored cache of the pinned vaults in the manifest.

``fetch_vault`` is idempotent: a cache entry already sitting on the pinned SHA costs one local
``git rev-parse`` and no network work at all. Anything else (missing entry, wrong commit) is
brought to the pin by clone/fetch/checkout. The cache root is a parameter, not a constant — the
repo's default is ``.corpus-cache/`` (see ``.gitignore``), but nothing here hardcodes it.

This is a sibling harness module, not part of the graphmark engine.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .manifest import CorpusVault


def _head_sha(target: Path) -> str | None:
    """Return the commit ``target`` is checked out at, or ``None`` if it is not a git repo."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _fetch_pinned_commit(target: Path, vault: CorpusVault) -> None:
    """Make ``vault.sha`` available in ``target``, cheapest viable fetch first.

    A shallow by-SHA fetch is the cheapest way to land one pinned commit, but it only resolves
    where the remote serves arbitrary SHAs in want — so its failure is expected, not an error,
    and the full by-SHA fetch is the fallback.
    """
    shallow = subprocess.run(
        ["git", "fetch", "--depth", "1", "origin", vault.sha],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if shallow.returncode == 0:
        return
    subprocess.run(["git", "fetch", "origin", vault.sha], check=True, cwd=target)


def fetch_vault(vault: CorpusVault, cache_root: Path) -> None:
    """Ensure ``cache_root / vault.name`` is a checkout of ``vault`` at its pinned SHA.

    Returns immediately — before any network operation — when the entry is already correct.
    """
    target = Path(cache_root) / vault.name

    if target.is_dir() and _head_sha(target) == vault.sha:
        return

    if not target.exists():
        cache_root = Path(cache_root)
        cache_root.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", vault.clone_url, vault.name],
            check=True,
            cwd=cache_root,
        )

    _fetch_pinned_commit(target, vault)
    subprocess.run(["git", "checkout", vault.sha], check=True, cwd=target)
