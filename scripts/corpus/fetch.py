"""Corpus fetch — populate a local, gitignored cache of the pinned vaults in the manifest.

``fetch_vault`` is idempotent: a cache entry already sitting on the pinned SHA costs one local
``git rev-parse`` and no network work at all. A missing entry is brought to the pin by
init/fetch/checkout. An existing entry sitting on the wrong commit is corrected by checkout
alone, skipping the fetch, when the pinned SHA is already a local git object (e.g. a pin this
entry was populated at earlier); otherwise it is fetched first, same as before. The cache root is a
parameter, not a constant — the repo's default is ``.corpus-cache/`` (see ``.gitignore``), but
nothing here hardcodes it.

This is a sibling harness module, not part of the graphmark engine.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .manifest import CorpusVault


def _head_sha(target: Path) -> str | None:
    """Return the commit ``target`` is checked out at, or ``None`` if it is not yet a git repo.

    Distinguishes "never a repo" from "was a repo, git failed": a ``target`` with no ``.git``
    entry returns ``None`` (needs clone/reinit). A ``target`` that does have a ``.git`` entry but
    where ``git rev-parse HEAD`` still fails raises ``ValueError`` instead -- collapsing that case
    to ``None`` would hide a real failure (permissions, corruption, ...) behind the same signal as
    "not yet populated".
    """
    if not (target / ".git").exists():
        return None
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(
            f"git rev-parse HEAD failed in existing repo at {target}: {result.stderr.strip()}"
        )
    return result.stdout.strip()


def _is_repo_root(target: Path) -> bool:
    """Return whether ``target`` is the top-level directory of its own git repository.

    Git walks up the directory tree looking for ``.git``, so a ``target`` that exists but is not
    itself a repo root (e.g. a stray leftover directory nested inside some unrelated, enclosing
    repo) would otherwise let git commands run with ``cwd=target`` silently operate on that
    enclosing repo instead of failing. Both sides are resolved before comparing -- ``git rev-parse
    --show-toplevel`` can differ from ``target`` by symlink normalization alone (e.g. macOS
    ``/tmp`` vs ``/private/tmp``), which would false-positive on a plain string comparison.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    return Path(result.stdout.strip()).resolve() == target.resolve()


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
    try:
        subprocess.run(["git", "fetch", "origin", vault.sha], check=True, cwd=target)
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"git fetch failed for corpus vault {vault.name!r} at {target}: exit {exc.returncode}"
        ) from exc


def _sha_is_local(target: Path, sha: str) -> bool:
    """Return whether ``sha`` already resolves to a local commit object in ``target``.

    Non-mutating (``git cat-file -e``, no ``check=True``): a nonzero exit means "not local, go
    fetch" -- an expected outcome, not an error -- so this never raises.
    """
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        cwd=target,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def fetch_vault(vault: CorpusVault, cache_root: Path) -> None:
    """Ensure ``cache_root / vault.name`` is a checkout of ``vault`` at its pinned SHA.

    Returns immediately — before any network operation — when the entry is already correct.
    """
    target = Path(cache_root) / vault.name

    if target.exists() and not target.is_dir():
        raise ValueError(
            f"corpus cache target for vault {vault.name!r} exists but is not a directory: {target}"
        )

    if target.is_dir() and _head_sha(target) == vault.sha:
        return

    if target.is_dir() and not _is_repo_root(target):
        raise ValueError(
            f"corpus cache target for vault {vault.name!r} is not the root of its own git "
            f"repository (found a directory nested inside an unrelated repo?): {target}"
        )

    fresh_entry = not target.exists()
    if fresh_entry:
        cache_root = Path(cache_root)
        cache_root.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(
                ["git", "init", vault.name],
                check=True,
                cwd=cache_root,
            )
            subprocess.run(
                ["git", "remote", "add", "origin", vault.clone_url],
                check=True,
                cwd=target,
            )
        except subprocess.CalledProcessError as exc:
            raise ValueError(
                f"git init/remote add failed for corpus vault {vault.name!r} at {target}: "
                f"exit {exc.returncode}"
            ) from exc

    try:
        subprocess.run(
            ["git", "remote", "set-url", "origin", vault.clone_url],
            check=True,
            cwd=target,
        )
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"git remote set-url failed for corpus vault {vault.name!r} at {target}: "
            f"exit {exc.returncode}"
        ) from exc

    if fresh_entry or not _sha_is_local(target, vault.sha):
        _fetch_pinned_commit(target, vault)
    try:
        subprocess.run(["git", "checkout", "--force", vault.sha], check=True, cwd=target)
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            f"git checkout failed for corpus vault {vault.name!r} at {target}: "
            f"exit {exc.returncode}"
        ) from exc
