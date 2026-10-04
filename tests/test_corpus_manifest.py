"""Tests for scripts/corpus/manifest.py: load_manifest unit tests and the real manifest's shape.

No network access anywhere here — the real manifest is a static TOML checked into the repo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.corpus.manifest import CorpusVault, load_manifest

REPO_ROOT = Path(__file__).parent.parent

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


def test_case_insensitive_duplicate_name_raises(tmp_path):
    # Two entries whose names differ only by case must be rejected too: on case-insensitive
    # filesystems (macOS/APFS default, Windows) they'd resolve to the same checkout directory in
    # fetch.py, silently clobbering each other. The message must name both original-case entries,
    # not just one, so a fix that only case-folds the comparison but keeps a single-name message
    # still fails this test.
    manifest_path = tmp_path / "manifest.toml"
    first = _VALID_ENTRY.replace('name = "example-vault"', 'name = "Example-Vault"')
    second = _VALID_ENTRY  # name = "example-vault"
    manifest_path.write_text(first + second)

    with pytest.raises(ValueError, match="duplicate vault name") as exc_info:
        load_manifest(manifest_path)

    assert "Example-Vault" in str(exc_info.value)
    assert "example-vault" in str(exc_info.value)


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


def test_traversal_name_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "../escape"
clone_url = "https://github.com/example/vault"
sha = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="invalid vault name"):
        load_manifest(manifest_path)


def test_separator_name_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "sub/dir"
clone_url = "https://github.com/example/vault"
sha = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="invalid vault name"):
        load_manifest(manifest_path)


def test_backslash_name_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = 'sub\\dir'
clone_url = "https://github.com/example/vault"
sha = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="invalid vault name"):
        load_manifest(manifest_path)


@pytest.mark.parametrize("name", ["..", "."])
def test_bare_dot_segment_name_raises(tmp_path, name):
    # Separator-free on purpose: "../escape" is already caught by the "/" check, so only a bare
    # ".." proves the traversal clause itself, and "." would make the cache target the cache root.
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text(f"""
[[vault]]
name = "{name}"
clone_url = "https://github.com/example/vault"
sha = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="invalid vault name"):
        load_manifest(manifest_path)


def test_malformed_sha_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "example-vault"
clone_url = "https://github.com/example/vault"
sha = "not-a-real-sha!!"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="malformed sha"):
        load_manifest(manifest_path)


def test_abbreviated_sha_raises(tmp_path):
    # A 12-char abbreviated sha is valid hex but not 40 chars: it must still be rejected, since
    # fetch.py's idempotent-fetch check does a full-string comparison against vault.sha.
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "example-vault"
clone_url = "https://github.com/example/vault"
sha = "0123456789ab"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="malformed sha"):
        load_manifest(manifest_path)


def test_clone_url_leading_dash_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "example-vault"
clone_url = "--upload-pack=touch /tmp/x"
sha = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match=r"starting with '-'"):
        load_manifest(manifest_path)


def test_excluded_dirs_bare_string_raises(tmp_path):
    # A bare string is valid TOML but not the required list: tuple(".git") would otherwise
    # silently explode into ('.', 'g', 'i', 't') instead of raising.
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "example-vault"
clone_url = "https://github.com/example/vault"
sha = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"
excluded_dirs = ".git"
""")

    with pytest.raises(ValueError, match="excluded_dirs that is not a list of strings"):
        load_manifest(manifest_path)


def test_excluded_dirs_non_string_element_raises(tmp_path):
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text("""
[[vault]]
name = "example-vault"
clone_url = "https://github.com/example/vault"
sha = "0123456789abcdef0123456789abcdef01234567"
license = "MIT"
excluded_dirs = [1, 2]
""")

    with pytest.raises(ValueError, match="excluded_dirs that is not a list of strings"):
        load_manifest(manifest_path)


def test_excluded_dirs_shape_check_runs_before_the_duplicate_name_check(tmp_path):
    # An entry that is both a duplicate and malformed must report the shape error: the shape
    # check sits with the other per-entry shape checks, ahead of the cross-entry dedup check.
    manifest_path = tmp_path / "manifest.toml"
    malformed_duplicate = _VALID_ENTRY.replace(
        'excluded_dirs = [".git", ".obsidian"]', 'excluded_dirs = ".git"'
    )
    manifest_path.write_text(_VALID_ENTRY + malformed_duplicate)

    with pytest.raises(ValueError, match="excluded_dirs that is not a list of strings"):
        load_manifest(manifest_path)


@pytest.mark.parametrize("empty_key", ["sha", "clone_url"])
def test_empty_field_raises_before_new_shape_checks(tmp_path, empty_key):
    # An empty sha/clone_url must still hit the pre-existing "empty required field" error, not the
    # new malformed-sha / leading-dash shape checks — same precedence as before this change.
    values = {
        "clone_url": "https://github.com/example/vault",
        "sha": "0123456789abcdef0123456789abcdef01234567",
    }
    values[empty_key] = ""
    manifest_path = tmp_path / "manifest.toml"
    manifest_path.write_text(f"""
[[vault]]
name = "example-vault"
clone_url = "{values["clone_url"]}"
sha = "{values["sha"]}"
license = "MIT"
excluded_dirs = [".git", ".obsidian"]
""")

    with pytest.raises(ValueError, match="empty required field"):
        load_manifest(manifest_path)


def test_link_syntax_key_loads_and_defaults(tmp_path):
    # An entry that sets link_syntax loads it verbatim; an entry that omits it (like every real
    # manifest entry today) must still default to "wikilink" — the pre-existing behavior — not
    # be rejected as missing a required field.
    manifest_path = tmp_path / "manifest.toml"
    with_syntax = (
        _VALID_ENTRY.replace('name = "example-vault"', 'name = "markdown-vault"')
        + '\nlink_syntax = "markdown"\n'
    )
    manifest_path.write_text(_VALID_ENTRY + with_syntax)

    vaults = load_manifest(manifest_path)
    by_name = {v.name: v for v in vaults}

    assert by_name["example-vault"].link_syntax == "wikilink"
    assert by_name["markdown-vault"].link_syntax == "markdown"


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
