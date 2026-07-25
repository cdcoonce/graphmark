"""diagnose(..., suggest=k) — near-miss candidates for a link that names nothing.

The last thing keeping a consumer's parallel resolver alive: when a link resolves to nothing, a
useful tool offers near-miss note titles, and the repair proposal is only actionable because of
them.

The rule here was not invented — it was calibrated against a frozen baseline of a real 521-note
vault's broken links, annotated by a human as useful / useless / missing-the-obvious-answer (see
tests/fixtures/suggest/README.md). Three policy decisions came from that annotation:

  1. A display matching more than SUGGEST_MAX_MATCHES notes gets nothing: it names a topic, not a
     typo. ([[AMRT]] matched 47 notes under the old rule.)
  2. A note whose stem is generic (SKILL.md, README.md) is indexed by its PARENT FOLDER, because
     that is where its name lives.
  3. Matching is directional. A display inside a candidate is an abbreviation and always useful
     ([[Jordan]] -> Jordan Ellis). A candidate inside a display is useful only when it covers
     most of it ([[fable-prompt-technique-reference]] -> fable-prompt-technique) and is noise when
     it is one word out of many ([[Dagster PJM InSchedules]] -> Dagster).

Partial overlap in neither direction is rejected: it produced no useful hint anywhere in the
baseline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphmark.config import VaultConfig
from graphmark.graph import (
    SUGGEST_MAX_MATCHES,
    SUGGEST_MIN_COVERAGE,
    NormalizeResolver,
    VaultGraph,
    diagnose,
)
from graphmark.parse import WikilinkExtractor


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestDefaultIsUnchanged:
    """suggest=0 must cost nothing — the check gate's hot path never wants suggestions."""

    def test_no_suggestions_without_the_flag(self, tmp_path):
        _write(tmp_path, "Jordan Ellis.md")
        _write(tmp_path, "a.md", "See [[Jordan]].\n")
        d = diagnose(_build(tmp_path), "Jordan")
        assert (d.reason, d.candidates) == ("missing", ())

    def test_explicit_zero_is_the_same(self, tmp_path):
        _write(tmp_path, "Jordan Ellis.md")
        assert diagnose(_build(tmp_path), "Jordan", suggest=0).candidates == ()


class TestAbbreviations:
    """display ⊆ candidate — the display names part of a longer real title."""

    def test_a_first_name_finds_the_full_name(self, tmp_path):
        _write(tmp_path, "people/Jordan Ellis.md")
        d = diagnose(_build(tmp_path), "Jordan", suggest=5)
        assert d.reason == "missing"
        assert d.candidates == ("people/Jordan Ellis.md",)

    def test_a_title_finds_a_prefixed_slug(self, tmp_path):
        _write(tmp_path, "ref/anthropic-containing-claude.md")
        d = diagnose(_build(tmp_path), "Containing Claude", suggest=5)
        assert d.candidates == ("ref/anthropic-containing-claude.md",)

    def test_date_prefixes_are_not_content(self, tmp_path):
        # A dated twin of the same note is the single most common shape in the baseline.
        _write(tmp_path, "notes/2026-04-11-mood-tracker.md")
        d = diagnose(_build(tmp_path), "Mood Tracker", suggest=5)
        assert d.candidates == ("notes/2026-04-11-mood-tracker.md",)

    def test_a_dated_twin_outranks_a_longer_untitled_match(self, tmp_path):
        # Where dropping digits actually bites: both notes contain the display's tokens, so both
        # match either way, but only ignoring the date makes the dated twin score a perfect 1.0
        # and sort first. Counting "2026", "04" and "11" as content buries the right answer.
        _write(tmp_path, "notes/2026-04-11-mood-tracker.md")
        _write(tmp_path, "notes/mood tracker notes.md")
        d = diagnose(_build(tmp_path), "Mood Tracker", suggest=5)
        assert d.candidates[0] == "notes/2026-04-11-mood-tracker.md"

    def test_punctuation_differences_do_not_matter(self, tmp_path):
        _write(tmp_path, "trips/2026-mike-brenna-wedding-trip.md")
        d = diagnose(_build(tmp_path), "Mike & Brenna Wedding Trip", suggest=5)
        assert d.candidates == ("trips/2026-mike-brenna-wedding-trip.md",)

    def test_several_expansions_all_surface(self, tmp_path):
        # [[Robin]] is genuinely ambiguous between two people — both must show, or the human
        # cannot pick.
        _write(tmp_path, "people/Robin Vance.md")
        _write(tmp_path, "people/Robin Weaver.md")
        d = diagnose(_build(tmp_path), "Robin", suggest=5)
        assert d.candidates == ("people/Robin Vance.md", "people/Robin Weaver.md")


class TestSuffixDrops:
    """candidate ⊆ display — useful only when the candidate covers most of the display."""

    def test_dropping_a_suffix_finds_the_base_note(self, tmp_path):
        _write(tmp_path, "ref/fable-prompt-technique.md")
        d = diagnose(_build(tmp_path), "fable-prompt-technique-reference", suggest=5)
        assert d.candidates == ("ref/fable-prompt-technique.md",)

    def test_a_two_word_display_finds_its_one_word_note(self, tmp_path):
        # [[Work Tasks]] -> work/Tasks.md: coverage 1/2 clears the floor.
        _write(tmp_path, "work/Tasks.md")
        d = diagnose(_build(tmp_path), "Work Tasks", suggest=5)
        assert d.candidates == ("work/Tasks.md",)

    def test_one_word_out_of_many_is_rejected(self, tmp_path):
        # [[Dagster PJM InSchedules]] -> Dagster was the archetypal noise hint: a real note, but
        # not the target, and it invites a wrong repair.
        _write(tmp_path, "ref/Dagster.md")
        d = diagnose(_build(tmp_path), "Dagster PJM InSchedules", suggest=5)
        assert d.candidates == ()

    def test_the_coverage_floor_is_the_boundary(self, tmp_path):
        # 2 of 5 tokens = 0.4, exactly the floor, which is inclusive.
        _write(tmp_path, "ref/rec dashboard.md")
        d = diagnose(_build(tmp_path), "reference rec dashboard env delivery", suggest=5)
        assert d.candidates == ("ref/rec dashboard.md",)
        # 1 of 5 = 0.2, below it.
        _write(tmp_path, "ref/delivery.md")
        assert (
            "ref/delivery.md"
            not in diagnose(
                _build(tmp_path), "reference rec dashboard env delivery", suggest=5
            ).candidates
        )


class TestPartialOverlapRejected:
    def test_sharing_one_token_in_neither_direction_suggests_nothing(self, tmp_path):
        # {graphify, memory, layer, eval} vs {graphify, knowledge, graph, tool}: neither is a
        # subset, so this is rejected. A known miss, accepted to keep the noise floor at zero.
        _write(tmp_path, "ideas/graphify-memory-layer-eval.md")
        d = diagnose(_build(tmp_path), "graphify-knowledge-graph-tool", suggest=5)
        assert d.candidates == ()


class TestBroadMatchSuppression:
    def test_a_display_matching_more_than_the_cap_suggests_nothing(self, tmp_path):
        for i in range(SUGGEST_MAX_MATCHES + 1):
            _write(tmp_path, f"notes/amrt topic {i}.md")
        d = diagnose(_build(tmp_path), "AMRT", suggest=5)
        assert d.candidates == ()

    def test_exactly_at_the_cap_still_suggests(self, tmp_path):
        for i in range(SUGGEST_MAX_MATCHES):
            _write(tmp_path, f"notes/amrt topic {i}.md")
        d = diagnose(_build(tmp_path), "AMRT", suggest=SUGGEST_MAX_MATCHES)
        assert len(d.candidates) == SUGGEST_MAX_MATCHES


class TestFolderNamedNotes:
    def test_a_generic_stem_is_indexed_by_its_folder(self, tmp_path):
        _write(tmp_path, "skills/mr-review-packet/SKILL.md")
        d = diagnose(_build(tmp_path), "mr-review-packet", suggest=5)
        assert d.candidates == ("skills/mr-review-packet/SKILL.md",)

    def test_readme_counts_as_generic_too(self, tmp_path):
        _write(tmp_path, "tools/link-checker/README.md")
        d = diagnose(_build(tmp_path), "link checker", suggest=5)
        assert d.candidates == ("tools/link-checker/README.md",)

    def test_a_normal_stem_is_still_indexed_by_its_stem(self, tmp_path):
        _write(tmp_path, "skills/mr-review-packet/notes.md")
        assert diagnose(_build(tmp_path), "mr-review-packet", suggest=5).candidates == ()

    def test_index_is_not_generic(self, tmp_path):
        # personal/Index.md is a real, linkable vault index — treating "Index" as generic would
        # re-key four different indexes onto their folder names and lose the actual answer.
        _write(tmp_path, "personal/Index.md")
        d = diagnose(_build(tmp_path), "Personal Index", suggest=5)
        assert d.candidates == ("personal/Index.md",)


class TestOrderingAndLimits:
    def test_k_limits_the_result(self, tmp_path):
        for name in ("Robin Vance", "Robin Weaver", "Robin Zhang"):
            _write(tmp_path, f"people/{name}.md")
        assert len(diagnose(_build(tmp_path), "Robin", suggest=2).candidates) == 2

    def test_best_coverage_ranks_first(self, tmp_path):
        _write(tmp_path, "a/afk-cockpit-ui.md")
        _write(tmp_path, "a/afk-cockpit-metrics-audit-and-review.md")
        d = diagnose(_build(tmp_path), "afk-cockpit", suggest=5)
        assert d.candidates[0] == "a/afk-cockpit-ui.md"

    def test_ties_break_on_rel_path(self, tmp_path):
        _write(tmp_path, "zeta/Robin Vance.md")
        _write(tmp_path, "alpha/Robin Ford.md")
        d = diagnose(_build(tmp_path), "Robin", suggest=5)
        assert d.candidates == ("alpha/Robin Ford.md", "zeta/Robin Vance.md")


class TestOnlyForMissing:
    """Every other verdict already carries the right candidates, or needs none."""

    def test_a_resolved_link_gets_no_suggestions(self, tmp_path):
        _write(tmp_path, "b.md")
        _write(tmp_path, "b extended.md")
        d = diagnose(_build(tmp_path), "b", suggest=5)
        assert (d.reason, d.candidates) == ("resolved", ())

    def test_an_ambiguous_link_keeps_its_real_candidates(self, tmp_path):
        _write(tmp_path, "one/note.md")
        _write(tmp_path, "two/note.md")
        _write(tmp_path, "three/note extended.md")
        d = diagnose(_build(tmp_path), "note", suggest=5)
        assert d.reason == "ambiguous"
        assert d.candidates == ("one/note.md", "two/note.md")

    def test_an_out_of_scope_link_keeps_its_real_candidates(self, tmp_path):
        _write(tmp_path, "docs/a.md")
        _write(tmp_path, "templates/guide.md")
        _write(tmp_path, "docs/guide extended.md")
        d = diagnose(_build(tmp_path, scoped_folders=["docs"]), "guide", suggest=5)
        assert d.reason == "out-of-scope-note"
        assert d.candidates == ("templates/guide.md",)

    def test_an_intra_note_link_gets_no_suggestions(self, tmp_path):
        _write(tmp_path, "a.md")
        assert diagnose(_build(tmp_path), "#Heading", suggest=5).candidates == ()

    def test_a_non_note_file_gets_no_suggestions(self, tmp_path):
        _write(tmp_path, "a.md")
        _write(tmp_path, "Board extended.md")
        assert diagnose(_build(tmp_path), "Board.canvas", suggest=5).candidates == ()


class TestConstants:
    def test_the_calibrated_band_is_published(self):
        # Both values were fixed by the annotated baseline, not chosen by taste: the cap at 12
        # because [[Priya Raghavan]] needs it (that token appears in 9 stems), the floor at 0.4
        # because it is the highest value that keeps every useful hint.
        assert SUGGEST_MAX_MATCHES == 12
        assert SUGGEST_MIN_COVERAGE == 0.4

    def test_exported_from_the_top_level(self):
        import graphmark

        assert graphmark.SUGGEST_MAX_MATCHES == SUGGEST_MAX_MATCHES
        assert graphmark.SUGGEST_MIN_COVERAGE == SUGGEST_MIN_COVERAGE


class TestBuildIsUnaffected:
    def test_suggestions_never_change_the_graph(self, tmp_path):
        _write(tmp_path, "hub.md", "[[Jordan]] and [[b]]\n")
        _write(tmp_path, "Jordan Ellis.md")
        _write(tmp_path, "b.md")
        graph = _build(tmp_path)
        assert graph.unresolved == {"hub.md": ["Jordan"]}
        assert graph.out_links["hub.md"] == {"b.md"}
        # asking for suggestions is a read, not a mutation
        diagnose(graph, "Jordan", suggest=5)
        assert graph.unresolved == {"hub.md": ["Jordan"]}
        assert graph.out_links["hub.md"] == {"b.md"}


@pytest.mark.parametrize("bad", [-1, -5])
def test_negative_suggest_is_a_usage_error(tmp_path, bad):
    _write(tmp_path, "a.md")
    with pytest.raises(ValueError, match="suggest"):
        diagnose(_build(tmp_path), "Nowhere", suggest=bad)
