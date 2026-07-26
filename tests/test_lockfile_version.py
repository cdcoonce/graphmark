"""The lockfile's root-package version must match pyproject's.

Not a style check. python-semantic-release bumps `pyproject.toml` on release
but does not re-lock, so `uv.lock` silently falls a version behind each time.
The next local `uv` invocation regenerates it, dirtying the working tree —
which aborts the nightly afk cycle on its clean-tree preflight. That drift ran
four releases deep (lock said 0.5.0 while the project was 0.9.0) before anyone
noticed, because nothing failed loudly.

This test is the loud failure. It holds whatever mechanism keeps the lockfile
current, so if the release workflow's relock step regresses, the gate says so
instead of the nightly quietly stopping.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version() -> str:
    data = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return data["project"]["version"]


def _locked_root_version() -> str:
    """Read the version uv.lock records for this project's own package."""
    lock = tomllib.loads((REPO_ROOT / "uv.lock").read_text(encoding="utf-8"))
    for package in lock["package"]:
        if package["name"] == "graphmark":
            return package["version"]
    raise AssertionError("uv.lock has no entry for the graphmark package")


def test_lockfile_records_the_current_project_version() -> None:
    assert _locked_root_version() == _pyproject_version(), (
        "uv.lock is stale relative to pyproject.toml. A release bumped the "
        "version without re-locking; run `uv lock` and commit the result."
    )


def test_release_workflow_relocks_and_stages_the_lockfile() -> None:
    """The mechanism, not just the outcome.

    Asserting only version agreement would stay green for a whole release
    cycle after the relock step was removed — the drift appears at the *next*
    release, long after the change that caused it.
    """
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    build_command = re.search(r'build_command\s*=\s*"""(.*?)"""', pyproject, re.DOTALL)

    assert build_command, "semantic_release.build_command must be a block string"
    body = build_command.group(1)
    assert "uv lock" in body, "release must re-lock after the version bump"
    assert "git add uv.lock" in body, (
        "the relocked file must be staged, or it is not part of the bump commit"
    )


def test_relock_targets_this_projects_actual_package_name() -> None:
    """The hardcoded package name must match the real one.

    `uv lock --upgrade-package <name>` does NOT fail on an unknown package —
    verified directly: `uv lock --upgrade-package graphmarkk` exits 0 and
    changes nothing. So renaming the project would silently disable the relock
    with no error anywhere, and the drift would only resurface a release later,
    looking like a fresh bug.

    Tying the literal to `project.name` makes a rename fail here, immediately,
    instead of in the next release's aftermath.
    """
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    data = tomllib.loads(pyproject_text)
    name = data["project"]["name"]

    build_command = re.search(r'build_command\s*=\s*"""(.*?)"""', pyproject_text, re.DOTALL)
    assert build_command
    assert f"uv lock --upgrade-package {name}" in build_command.group(1), (
        f"build_command must relock the real package name ({name!r}); "
        "uv silently no-ops on an unknown one"
    )
