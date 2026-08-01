"""Tests for scripts/corpus/manifest.py: load_manifest unit tests and the real manifest's shape.

No network access anywhere here — the real manifest is a static TOML checked into the repo.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.corpus.manifest import CorpusVault, load_manifest  # noqa: E402

REAL_MANIFEST = REPO_ROOT / "docs" / "corpus" / "manifest.toml"

_VALID_ENTRY = """
[[vault]]
name = "example-vault"
clone_url = "https://github.com/example/vault"
sha = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
"""


def test_parses_synthetic_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text(_VALID_ENTRY)

    vaults = load_manifest(manifest_path)

    assert vaults == [
        CorpusVault(
            name="example-vault",
            clone_url="https://github.com/example/vault",
            sha="0123456789abcdef0123456789abcdef01234567",
            license="MIT",
            excluded_dirs=(".git", ".obsidian"),
        )
    ]


def test_duplicate_name_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text(_VALID_ENTRY + _VALID_ENTRY)

    with pytest.raises(ValueError, match="duplicate vault name"):
        load_manifest(manifest_path)


def test_missing_required_field_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "example-vault"
clone_url = "https://github.com/example/vault"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="missing required field"):
        load_manifest(manifest_path)


def test_empty_required_field_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "example-vault"
clone_url = "https://github.com/example/vault"
sha = ""
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="empty required field"):
        load_manifest(manifest_path)


def test_real_manifest_loads():
    vaults = load_manifest(REAL_MANIFEST)

    assert len(vaults) == 8
    names = [v.name for v in vaults]
    assert len(names) == len(set(names))


def test_real_manifest_shas_are_40_lowercase_hex_chars():
    vaults = load_manifest(REAL_MANIFEST)

    for vault in vaults:
        assert re.fullmatch(r"[0-9a-f]{40}", vault.sha), vault.sha


def test_real_manifest_entries_have_non_empty_sha_and_license():
    vaults = load_manifest(REAL_MANIFEST)

    for vault in vaults:
        assert vault.sha
        assert vault.license
