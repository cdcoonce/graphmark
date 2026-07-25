"""Per-reason link counts and the conservation law — Track F's foundation.

`build` sorts every extracted display into one of the six `DIAGNOSIS_REASONS`, then keeps the
result of exactly one bucket (`unresolved`) plus the edges. The other outcomes are decided and
discarded, and that silence is why six of the seven correctness bugs in this package's history went
unnoticed: each was a *mis-bucketing* — a link filed as `unresolved` that belonged in `resolved`, or
the reverse — and nothing in the output made an implausible distribution visible.

The conservation law is the backbone: **nothing may vanish silently.** Every display the extractor
produces lands in exactly one bucket, and the buckets sum to the extraction count. Every one of the
seven bugs violated that in spirit.
"""

from __future__ import annotations

from pathlib import Path

from graphmark.config import VaultConfig
from graphmark.graph import DIAGNOSIS_REASONS, NormalizeResolver, VaultGraph
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


def _extracted_total(root: Path, graph: VaultGraph) -> int:
    """Every display the extractor produces across the notes actually in the graph."""
    extractor = WikilinkExtractor()
    return sum(len(extractor.extract(doc.text)) for doc in graph.nodes.values())


class TestShape:
    def test_all_six_reasons_are_always_present(self, tmp_path):
        # A zero is a finding — "0 alias-resolved on a vault full of aliases" is the whole point —
        # so a bucket must never be absent just because nothing landed in it.
        _write(tmp_path, "a.md", "No links here.\n")
        counts = _build(tmp_path).link_counts
        assert set(counts) == set(DIAGNOSIS_REASONS)
        assert all(v == 0 for v in counts.values())

    def test_key_order_matches_diagnosis_reasons(self, tmp_path):
        # This feeds a byte-stable report, so ordering is contract, not incidental.
        _write(tmp_path, "a.md", "[[Nowhere]]\n")
        assert tuple(_build(tmp_path).link_counts) == DIAGNOSIS_REASONS

    def test_an_empty_vault_still_reports_every_bucket(self, tmp_path):
        vault = tmp_path / "empty"
        vault.mkdir()
        assert tuple(_build(vault).link_counts) == DIAGNOSIS_REASONS

    def test_directly_constructed_graph_defaults_to_empty(self):
        graph = VaultGraph(nodes={}, out_links={}, back_links={})
        assert graph.link_counts == {}
        assert graph.alias_resolved == 0


class TestCounting:
    def test_each_reason_is_counted(self, tmp_path):
        _write(
            tmp_path,
            "docs/hub.md",
            "\n".join(
                [
                    "[[target]]",  # resolved
                    "[[note]]",  # ambiguous
                    "[[Chart.base]]",  # non-note-file
                    "[[CLAUDE]]",  # out-of-scope-note
                    "[[Nowhere]]",  # missing
                    "[[#Local]]",  # intra-note
                ]
            )
            + "\n",
        )
        _write(tmp_path, "docs/target.md")
        _write(tmp_path, "docs/one/note.md")
        _write(tmp_path, "docs/two/note.md")
        _write(tmp_path, "CLAUDE.md")
        graph = _build(tmp_path, scoped_folders=["docs"], rules_files=["CLAUDE.md"])
        assert graph.link_counts == {
            "resolved": 1,
            "ambiguous": 1,
            "non-note-file": 1,
            "out-of-scope-note": 1,
            "missing": 1,
            "intra-note": 1,
        }

    def test_occurrences_not_distinct_targets(self, tmp_path):
        # Matches unresolved_link_count's existing semantics: three [[Missing]] links are three.
        _write(tmp_path, "a.md", "[[Missing]] [[Missing]] [[Missing]]\n")
        assert _build(tmp_path).link_counts["missing"] == 3

    def test_a_resolved_self_link_counts_as_resolved(self, tmp_path):
        # It resolved; it is merely not an edge. Counting it anywhere else would make a
        # self-referential note look broken.
        _write(tmp_path, "solo.md", "I link to [[solo]].\n")
        graph = _build(tmp_path)
        assert graph.link_counts["resolved"] == 1
        assert graph.out_links["solo.md"] == set()

    def test_links_in_code_spans_are_not_counted(self, tmp_path):
        # They were never extracted, so they are not part of the accounting at all.
        _write(tmp_path, "a.md", "Inline `[[NotALink]]` and:\n\n```\n[[AlsoNot]]\n```\n")
        assert sum(_build(tmp_path).link_counts.values()) == 0

    def test_out_of_scope_notes_contribute_no_counts(self, tmp_path):
        # A note outside the graph is not part of the vault, so its links are not vault links.
        _write(tmp_path, "docs/a.md", "[[Nowhere]]\n")
        _write(tmp_path, "templates/t.md", "[[AlsoNowhere]] [[AndAnother]]\n")
        graph = _build(tmp_path, scoped_folders=["docs"])
        assert graph.link_counts["missing"] == 1


class TestAliasResolved:
    def test_alias_hits_are_counted_separately(self, tmp_path):
        _write(tmp_path, "n.md", "---\naliases:\n  - Nickname\n---\n")
        _write(tmp_path, "src.md", "See [[Nickname]].\n")
        graph = _build(tmp_path)
        assert graph.alias_resolved == 1
        # still a resolution, so it also lands in the resolved bucket — the counts are a
        # partition of outcomes, and alias_resolved is a lens on one of them, not a seventh bucket
        assert graph.link_counts["resolved"] == 1

    def test_stem_resolutions_are_not_counted_as_alias(self, tmp_path):
        _write(tmp_path, "b.md")
        _write(tmp_path, "src.md", "See [[b]].\n")
        graph = _build(tmp_path)
        assert graph.alias_resolved == 0
        assert graph.link_counts["resolved"] == 1

    def test_the_119_signature_is_visible(self, tmp_path):
        # The exact shape that hid for six releases: notes declare aliases, links use them, and
        # the distribution shows resolutions with zero of them via alias. With aliases disabled
        # those links land in `missing` instead — which is what the old defect looked like.
        _write(tmp_path, "n.md", "---\naliases:\n  - Nickname\n---\n")
        _write(tmp_path, "src.md", "See [[Nickname]].\n")
        broken = _build(tmp_path, resolve_aliases=False)
        assert broken.alias_resolved == 0
        assert broken.link_counts["missing"] == 1
        assert broken.link_counts["resolved"] == 0

    def test_alias_count_survives_a_directly_constructed_graph(self):
        assert (
            VaultGraph(nodes={}, out_links={}, back_links={}, alias_resolved=7).alias_resolved == 7
        )


class TestConservationLaw:
    """Nothing vanishes silently — the invariant every one of the seven bugs violated in spirit."""

    def test_buckets_sum_to_the_extraction_count(self, tmp_path):
        _write(
            tmp_path,
            "docs/hub.md",
            "[[target]] [[note]] [[Chart.base]] [[CLAUDE]] [[Nowhere]] [[#Local]] "
            "[[Nickname]] [[docs/deep/x]] [[target]]\n",
        )
        _write(tmp_path, "docs/target.md")
        _write(tmp_path, "docs/one/note.md")
        _write(tmp_path, "docs/two/note.md")
        _write(tmp_path, "docs/deep/x.md")
        _write(tmp_path, "docs/aliased.md", "---\naliases:\n  - Nickname\n---\n")
        _write(tmp_path, "CLAUDE.md")
        graph = _build(tmp_path, scoped_folders=["docs"], rules_files=["CLAUDE.md"])
        assert sum(graph.link_counts.values()) == _extracted_total(tmp_path, graph)

    def test_conservation_holds_on_a_vault_with_no_links(self, tmp_path):
        _write(tmp_path, "a.md", "Nothing here.\n")
        graph = _build(tmp_path)
        assert sum(graph.link_counts.values()) == _extracted_total(tmp_path, graph) == 0

    def test_unresolved_equals_ambiguous_plus_missing(self, tmp_path):
        # The new tally cannot disagree with the surface that already existed.
        _write(tmp_path, "docs/hub.md", "[[note]] [[Nowhere]] [[Gone]] [[target]]\n")
        _write(tmp_path, "docs/target.md")
        _write(tmp_path, "docs/one/note.md")
        _write(tmp_path, "docs/two/note.md")
        graph = _build(tmp_path, scoped_folders=["docs"])
        occurrences = sum(len(v) for v in graph.unresolved.values())
        assert occurrences == graph.link_counts["ambiguous"] + graph.link_counts["missing"]

    def test_edges_never_exceed_resolved(self, tmp_path):
        # Every edge came from a resolved display; self-links resolve without producing one, so
        # edges are a subset, never a superset.
        _write(tmp_path, "hub.md", "[[a]] [[b]] [[hub]] [[Nowhere]]\n")
        _write(tmp_path, "a.md")
        _write(tmp_path, "b.md")
        graph = _build(tmp_path)
        assert sum(len(v) for v in graph.out_links.values()) <= graph.link_counts["resolved"]

    def test_frozen_fixtures_conserve(self):
        from graphmark.config import load_config

        for name in ("simple", "alt", "scoped", "selflink"):
            cfg = load_config(Path(__file__).parent / "fixtures" / name / "config.toml")
            graph = VaultGraph.build(cfg, WikilinkExtractor(), NormalizeResolver())
            total = sum(len(WikilinkExtractor().extract(d.text)) for d in graph.nodes.values())
            assert sum(graph.link_counts.values()) == total, name
