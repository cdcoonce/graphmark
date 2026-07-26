"""Path-suffix resolution is indexed, not scanned (#157).

Every path-qualified display used to flatten the catalog and compare against **every** rel_path.
With wikilinks that branch is rare — most displays are bare names hitting a dict — so the `O(L·N)`
ceiling was documented and accepted. #152 changed which branch is hot: every markdown link is
path-qualified by construction, so the rare branch became the only branch. Measured on a 1120-note
vault with 10,149 markdown links: 2.9 s against 0.3 s for the same vault read as wikilinks.

Any legal suffix match must end with the display's final component, so bucketing paths by folded
filename is **exactly** equivalent to scanning them all — same matches, same order, same verdicts.
This file exists to hold that equivalence, since a pure speedup that changes one answer is a bug.
"""

from __future__ import annotations

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph, candidates_for
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **kw) -> VaultGraph:
    return VaultGraph.build(VaultConfig(root=root, **kw), WikilinkExtractor(), NormalizeResolver())


def _scan_resolve(display: str, catalog: dict[str, list[str]]) -> list[str]:
    """The pre-#157 behavior, written out: compare against every path, in flatten order.

    Kept as an independent reference rather than by calling the implementation, so the equivalence
    tests below compare two things instead of one thing with itself.
    """
    from graphmark.graph import _fold_case, _matches_path_suffix, _strip_display

    target = _strip_display(display)
    suffix = _fold_case(target) + ".md"
    return [p for paths in catalog.values() for p in paths if _matches_path_suffix(p, suffix)]


class TestEquivalence:
    """Same answers as the scan, on every shape that has ever mattered here."""

    def test_matches_the_scan_across_the_shapes_136_turned_on(self, tmp_path):
        for rel in (
            "work/Tasks.md",
            "homework/Tasks.md",
            "a/b/work/Tasks.md",
            "docs/Tasks.md",
            "api-docs/Tasks.md",
            "Tasks.md",
            "work/Other.md",
        ):
            _write(tmp_path, rel)
        catalog = _build(tmp_path).catalog
        resolver = NormalizeResolver()
        for display in (
            "work/Tasks",
            "homework/Tasks",
            "b/work/Tasks",
            "docs/Tasks",
            "Tasks",
            "work/Other",
            "nope/Tasks",
            "work/Nope",
        ):
            expected = sorted(_scan_resolve(display, catalog))
            assert sorted(candidates_for(display, catalog)) == expected, display
            if "/" in display:
                unique = expected[0] if len(expected) == 1 else None
                assert resolver.resolve(display, catalog) == unique, display

    def test_case_and_unicode_form_still_fold(self, tmp_path):
        _write(tmp_path, "Work/Tasks.md")
        catalog = _build(tmp_path).catalog
        assert NormalizeResolver().resolve("work/tasks", catalog) == "Work/Tasks.md"

    def test_a_genuine_collision_is_still_declined(self, tmp_path):
        _write(tmp_path, "a/work/Tasks.md")
        _write(tmp_path, "b/work/Tasks.md")
        catalog = _build(tmp_path).catalog
        assert NormalizeResolver().resolve("work/Tasks", catalog) is None
        assert candidates_for("work/Tasks", catalog) == ["a/work/Tasks.md", "b/work/Tasks.md"]

    def test_a_whole_path_and_a_deeper_suffix_both_match(self, tmp_path):
        # The case that forbids short-circuiting on an exact hit: "work/Tasks" names both, so the
        # resolver must decline. An index that returned the exact match would change the verdict.
        _write(tmp_path, "work/Tasks.md")
        _write(tmp_path, "a/work/Tasks.md")
        catalog = _build(tmp_path).catalog
        assert NormalizeResolver().resolve("work/Tasks", catalog) is None
        assert candidates_for("work/Tasks", catalog) == ["a/work/Tasks.md", "work/Tasks.md"]

    def test_a_degenerate_trailing_slash_display(self, tmp_path):
        _write(tmp_path, "a/b.md")
        catalog = _build(tmp_path).catalog
        assert candidates_for("a/", catalog) == _scan_resolve("a/", catalog)


class TestCacheSafety:
    def test_two_catalogs_do_not_share_an_index(self, tmp_path):
        _write(tmp_path, "one/note.md")
        first = _build(tmp_path).catalog
        _write(tmp_path, "two/other.md")
        second = _build(tmp_path).catalog
        resolver = NormalizeResolver()
        assert resolver.resolve("one/note", first) == "one/note.md"
        assert resolver.resolve("two/other", second) == "two/other.md"
        # Back to the first catalog: a single-slot cache must re-key, not answer from the second.
        assert resolver.resolve("two/other", first) is None
        assert resolver.resolve("one/note", first) == "one/note.md"

    def test_alternating_between_two_catalogs_does_not_rebuild(self):
        """The regression guard for what actually made the first attempt useless.

        `_diagnose` consults the in-scope catalog and the out-of-scope one for the same
        display, so a single-slot cache alternates and misses every time. That version rebuilt
        the index 29,265 times for 10,149 links and was no faster than the scan it replaced — a
        "speedup" that was entirely cache thrash. The buckets' identity is the observable.
        """
        from graphmark.graph import _FilenameIndex

        a = {"one": ["one/note.md"]}
        b = {"two": ["two/other.md"]}
        index = _FilenameIndex()
        first_a, first_b = index.for_catalog(a), index.for_catalog(b)
        for _ in range(5):
            assert index.for_catalog(a) is first_a
            assert index.for_catalog(b) is first_b

    def test_the_slot_count_is_bounded(self):
        # The cache holds catalogs alive, so it must not become an unbounded retainer.
        from graphmark.graph import _FilenameIndex

        index = _FilenameIndex()
        for i in range(_FilenameIndex._MAX_SLOTS + 3):
            index.for_catalog({f"k{i}": [f"f{i}/n.md"]})
        assert len(index._slots) <= _FilenameIndex._MAX_SLOTS

    def test_a_mutated_catalog_is_not_answered_from_a_stale_index(self, tmp_path):
        _write(tmp_path, "one/note.md")
        catalog = _build(tmp_path).catalog
        resolver = NormalizeResolver()
        assert resolver.resolve("one/note", catalog) == "one/note.md"
        # Same object, new content. The cache keys on identity, so this is its honest limit:
        # callers must not mutate a catalog mid-build. Asserted so the limit is visible.
        catalog.setdefault("late", []).append("late/late.md")
        assert resolver.resolve("late/late", catalog) is None
