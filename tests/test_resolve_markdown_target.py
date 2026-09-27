"""Direct unit tests for `resolve_markdown_target`'s edge cases (#277).

`resolve_markdown_target` is a pure function with a detailed docstring describing several
distinct behaviors, but no test in the repo calls it directly — it is only exercised indirectly
through full `VaultGraph.build()` runs, which makes these specific edge cases (bare-target
passthrough, root-escape detection, relative normalization) hard to pin down in isolation.

This module covers three of those behaviors: (1) with `autolinks=True`, a bare target (no `/`)
passes through unchanged; (2) a path-qualified target is normalized against `source_rel_path`'s
parent folder; (3) a target that normalizes to `..` or above the vault root returns `None`.

The fourth documented behavior — a leading-`/` target is vault-root-relative — postdates this
issue and is out of scope here (see the issue's Anti-scope).
"""

from __future__ import annotations

from graphmark.graph import resolve_markdown_target


class TestAutolinksBareTargetPassthrough:
    def test_bare_target_with_autolinks_passes_through_unchanged(self):
        assert resolve_markdown_target("note.md", "docs/x.md", autolinks=True) == "note.md"


class TestBareTargetWithoutAutolinksUsesRelativeBranch:
    def test_bare_target_without_autolinks_uses_relative_branch(self):
        # Without autolinks, even a bare target goes through the relative-path branch —
        # joined against source_rel_path's parent — instead of passing through unchanged.
        assert resolve_markdown_target("note.md", "docs/x.md", autolinks=False) == "docs/note.md"


class TestRootEscape:
    def test_target_escaping_vault_root_returns_none(self):
        assert resolve_markdown_target("../../outside.md", "x.md", autolinks=False) is None


class TestNormalRelativePath:
    def test_normal_relative_path_resolves_against_parent(self):
        assert (
            resolve_markdown_target("sub/note.md", "docs/x.md", autolinks=False)
            == "docs/sub/note.md"
        )
