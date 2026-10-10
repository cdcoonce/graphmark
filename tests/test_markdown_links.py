"""Markdown-style `[text](note.md)` links, config-gated (#152).

The roadmap lists alternate link-syntax adapters under non-goals with a precise escape hatch — "the
pluggable interfaces exist so these _can_ be added on demand; do not build them speculatively." The
second corpus run supplied the demand: `lyz-code/blue-book`, 1120 notes, 11,198 markdown-style links
(99% targeting a real note), zero extracted edges.

Four decisions this encodes, all reversible in config:

1. **Selection** is `link_syntax = "wikilink" | "markdown" | "both"`, defaulting to `"wikilink"`.
   Every existing vault, every frozen fixture and the reference vault are byte-identical untouched.
2. **Resolution is relative to the linking note**, which is genuinely new: a markdown target is a
   path, not a name. Rather than change the `Resolver` protocol — which never receives the source
   note, and which the roadmap forbids redesigning — the target is normalized into a vault-relative
   path *before* diagnosis, where the existing path branch resolves it exactly.
3. **No new frozen fixture.** The oracle is wikilink-only and regenerating it is a human's call
   (Track B); these are hand-written assertions instead.
4. **A target that escapes the vault root is `missing`**, not resolved and not an error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graphmark.config import VaultConfig
from graphmark.graph import NormalizeResolver, VaultGraph, diagnose
from graphmark.parse import MarkdownLinkExtractor, WikilinkExtractor, count_markdown_links


def _write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build(root: Path, **config_kwargs) -> VaultGraph:
    return VaultGraph.build(
        VaultConfig(root=root, **config_kwargs), WikilinkExtractor(), NormalizeResolver()
    )


class TestExtractor:
    def test_extracts_a_relative_target(self):
        assert MarkdownLinkExtractor().extract("[the note](other.md)") == ["other.md"]

    def test_keeps_the_target_not_the_display_text(self):
        assert MarkdownLinkExtractor().extract("[Some Title](a/b.md)") == ["a/b.md"]

    def test_drops_an_anchor(self):
        assert MarkdownLinkExtractor().extract("[x](note.md#Section)") == ["note.md"]

    def test_ignores_images_urls_and_non_markdown_targets(self):
        text = "![i](c.png) [u](https://x.com/a.md) [p](doc.pdf) [[Wiki]]"
        assert MarkdownLinkExtractor().extract(text) == []

    def test_ignores_code_spans_and_fences(self):
        assert MarkdownLinkExtractor().extract("`[a](n.md)`\n```\n[b](n.md)\n```\n") == []

    def test_decodes_percent_encoding(self):
        # Real markdown encodes spaces; the vault stores them literally.
        assert MarkdownLinkExtractor().extract("[x](my%20note.md)") == ["my note.md"]

    def test_recognizes_a_plain_target_unchanged(self):
        # #239 regression: the plain form's extraction must stay byte-identical.
        assert MarkdownLinkExtractor().extract("[text](note.md)") == ["note.md"]

    def test_recognizes_a_titled_link(self):
        # #239: a link title (`"Some Title"`) after the target must not swallow the whole match.
        assert MarkdownLinkExtractor().extract('[text](note.md "A Title")') == ["note.md"]

    def test_recognizes_an_angle_bracket_target(self):
        # #239: the standard CommonMark escape for a target containing spaces/parens.
        assert MarkdownLinkExtractor().extract("[text](<my note.md>)") == ["my note.md"]

    def test_recognizes_a_combined_angle_bracket_and_titled_target(self):
        # #239: angle-bracket target and title together.
        assert MarkdownLinkExtractor().extract('[text](<my note.md> "A Title")') == ["my note.md"]

    def test_an_anchor_containing_spaces_still_extracts(self):
        # Regression guard for #239: the pre-#239 pattern accepted any anchor text up to ")",
        # spaces included, with or without a trailing title. Supporting titles must not drop it.
        assert MarkdownLinkExtractor().extract("[text](note.md#My Section)") == ["note.md"]
        assert MarkdownLinkExtractor().extract('[text](note.md#My Section "T")') == ["note.md"]

    def test_extracts_an_uppercase_extension(self):
        # #261: `.MD` must match exactly like `.md`, matching the wikilink case-insensitive check.
        assert MarkdownLinkExtractor().extract("[text](Note.MD)") == ["Note.MD"]

    def test_extracts_a_mixed_case_extension_titled_and_angle_bracket(self):
        # #261, combined with #239 syntax: a titled, angle-bracket-escaped target with a mixed-case
        # extension must still match, and the target's original casing is preserved verbatim.
        assert MarkdownLinkExtractor().extract('[text](<my note.Md> "A Title")') == ["my note.Md"]


#: Separators that put a BLANK line between two lines: empty, spaces/tabs only, and the CRLF forms
#: of both. A blank line ends the paragraph, so no inline code span may reach across one.
BLANK_LINE_SEPARATORS = [
    pytest.param("\n\n", id="lf"),
    pytest.param("\n  \t\n", id="lf-spaces-and-tab"),
    pytest.param("\r\n\r\n", id="crlf"),
    pytest.param("\r\n \t\r\n", id="crlf-spaces-and-tab"),
]


class TestInlineCodeSpanForms:
    """Pins what an inline code span hides today (#289), before a span may wrap a line break.

    The markdown-link twin of the wikilink pins in test_parse.py: `MarkdownLinkExtractor` and
    `count_markdown_links` strip code through the same shared helper, and each is asserted so a
    change confined to one of the two paths cannot slip through. Every case is green on the
    single-line-only regex and has to stay green once a span may wrap one line break.
    """

    def test_a_single_line_span_hides_its_own_link_and_nothing_around_it(self):
        text = "Before [a](a.md) `[h](hidden.md)` after [b](b.md)."
        assert MarkdownLinkExtractor().extract(text) == ["a.md", "b.md"]
        assert count_markdown_links(text) == 2

    def test_text_between_two_spans_on_one_line_stays_visible(self):
        text = "`[x](x.md)` then [between](between.md) then `[y](y.md)`"
        assert MarkdownLinkExtractor().extract(text) == ["between.md"]
        assert count_markdown_links(text) == 1

    def test_adjacent_backticks_are_not_a_span_and_hide_nothing_after_them(self):
        text = "empty `` then [v](visible.md) to the end"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]
        assert count_markdown_links(text) == 1

    def test_a_lone_backtick_hides_nothing_on_its_own_line(self):
        text = "a stray ` then [v](visible.md) to the end"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]
        assert count_markdown_links(text) == 1

    def test_an_unterminated_backtick_hides_nothing_on_the_lines_after_it(self):
        # No closing backtick anywhere: the opener must not swallow the lines that follow it.
        text = "a stray `tick here\nthen [v](visible.md)\nto the end\n"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]
        assert count_markdown_links(text) == 1

    @pytest.mark.parametrize("sep", BLANK_LINE_SEPARATORS)
    def test_a_blank_line_between_two_backticks_ends_the_span(self, sep):
        # A blank line ends the paragraph, and with it any open backtick: both links stay visible.
        text = f"`[f](first.md) code with{sep}[s](second.md) more`"
        assert MarkdownLinkExtractor().extract(text) == ["first.md", "second.md"]
        assert count_markdown_links(text) == 2

    def test_a_crlf_single_line_span_hides_its_link_and_nothing_around_it(self):
        text = "Pre [a](a.md)\r\n`[h](hidden.md)` mid\r\nPost [b](b.md)\r\n"
        assert MarkdownLinkExtractor().extract(text) == ["a.md", "b.md"]
        assert count_markdown_links(text) == 2

    def test_a_span_next_to_a_fenced_block_hides_only_its_own_link(self):
        text = "`[h](hidden.md)`\n```\n[i](inside.md)\n```\n`[g](gone.md)` [v](visible.md)\n"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]
        assert count_markdown_links(text) == 1

    def test_prose_between_two_triple_backtick_spans_on_adjacent_lines_stays_visible(self):
        # A ```x``` run leaves two end backticks behind on each side. They must not pair across
        # the line break and hide the prose between the two spans (a real link).
        text = "- ```a```: see [r](real.md)\n- ```b```: more\n"
        assert MarkdownLinkExtractor().extract(text) == ["real.md"]
        assert count_markdown_links(text) == 1

    def test_a_backtick_run_longer_than_one_does_not_open_a_span_across_a_line_break(self):
        text = "``a [v](visible.md)\nb`"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]
        assert count_markdown_links(text) == 1

    def test_a_backtick_run_longer_than_one_does_not_close_a_span_across_a_line_break(self):
        text = "`a [v](visible.md)\nb``"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]
        assert count_markdown_links(text) == 1

    def test_an_escaped_backtick_does_not_open_a_span_across_a_line_break(self):
        # A backslash-escaped backtick is a literal, not a delimiter: the real span `x` on the
        # next line is the only code here, so the link before it stays visible.
        text = "type \\` then [v](visible.md)\nand `x` more"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]
        assert count_markdown_links(text) == 1


class TestInlineCodeSpanWrapsOneLineBreak:
    """An inline code span may wrap one line break (#289), for markdown links too.

    The markdown-link twin of the wikilink tests in test_parse.py. `MarkdownLinkExtractor` and
    `count_markdown_links` are asserted separately, and `count_markdown_links` by its exact value,
    so a change that fixes one path and leaves the other on the old behaviour is caught. A visible
    link next to the hidden one makes each test fail on a span that swallows its surroundings too.
    """

    def test_a_link_on_the_second_line_of_a_wrapped_span_is_hidden(self):
        text = "See `code with\n[text](note.md)` end."
        assert MarkdownLinkExtractor().extract(text) == []

    def test_a_link_on_the_first_line_of_a_wrapped_span_is_hidden(self):
        text = "See `[text](note.md) code\nmore` end."
        assert MarkdownLinkExtractor().extract(text) == []

    def test_a_link_on_the_second_line_of_a_crlf_wrapped_span_is_hidden(self):
        text = "See `code with\r\n[text](note.md)` end."
        assert MarkdownLinkExtractor().extract(text) == []

    def test_a_link_on_the_first_line_of_a_crlf_wrapped_span_is_hidden(self):
        text = "See `[text](note.md) code\r\nmore` end."
        assert MarkdownLinkExtractor().extract(text) == []

    @pytest.mark.parametrize(
        "text",
        [
            pytest.param("- Item `code with\n  [h](hidden.md)` end. [v](visible.md)", id="list"),
            pytest.param("- Item `code with\n\t[h](hidden.md)` end. [v](visible.md)", id="tab"),
            pytest.param("> Quote `code with\n> [h](hidden.md)` end. [v](visible.md)", id="quote"),
        ],
    )
    def test_a_wrapped_span_whose_second_line_is_indented_or_quoted_hides_its_link(self, text):
        # The hard-wrap shapes real notes use: a list item's indented continuation line, a tab,
        # and a blockquote's `> ` prefix. The second line need not start at column 0.
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]
        assert count_markdown_links(text) == 1

    def test_text_before_and_after_a_wrapped_span_stays_visible(self):
        text = "[b](before.md) See `code with\n[h](hidden.md)` end. [a](after.md)"
        assert MarkdownLinkExtractor().extract(text) == ["before.md", "after.md"]

    def test_a_link_between_two_wrapped_spans_stays_visible(self):
        text = "`a\n[h](one.md)` [v](between.md) `[h](two.md)\nb`"
        assert MarkdownLinkExtractor().extract(text) == ["between.md"]

    def test_a_link_between_a_wrapped_span_and_a_single_line_span_stays_visible(self):
        # The wrapped alternative must stop at its own closing backtick: a swallow tail that
        # reaches over the following single-line span would hide `between.md` too.
        text = "`a\n[h](one.md)` [v](between.md) `[h](two.md)`"
        assert MarkdownLinkExtractor().extract(text) == ["between.md"]
        assert count_markdown_links(text) == 1

    def test_a_link_between_a_single_line_span_and_a_wrapped_span_stays_visible(self):
        # The reverse order: the first line's run must stop at the nearest backtick, not run on to
        # the last one on its line and open a wrapped span there.
        text = "`[h](one.md)` [v](between.md) `a\n[h](two.md)`"
        assert MarkdownLinkExtractor().extract(text) == ["between.md"]
        assert count_markdown_links(text) == 1

    @pytest.mark.parametrize("eol", [pytest.param("\n", id="lf"), pytest.param("\r\n", id="crlf")])
    def test_an_opening_backtick_that_ends_its_line_wraps_nothing_under_either_line_ending(
        self, eol
    ):
        # Known limit: CommonMark would pair a backtick that ends its line with the closing one
        # on the next line, graphmark does not. What is pinned is that LF and CRLF agree: the
        # lone CR of a CRLF break must not stand in for the line's missing first character.
        text = f"- item `{eol}  [h](hidden.md)` end [v](visible.md)"
        assert MarkdownLinkExtractor().extract(text) == ["hidden.md", "visible.md"]
        assert count_markdown_links(text) == 2

    def test_a_link_on_the_line_after_a_wrapped_span_stays_visible(self):
        text = "`code with\n[h](hidden.md)`\n[v](visible.md)\n"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]

    def test_a_wrapped_span_and_a_blank_line_that_ends_a_span_in_one_text(self):
        text = "See `a\nb` and `c\n\n[v](visible.md) d`"
        assert MarkdownLinkExtractor().extract(text) == ["visible.md"]

    def test_count_excludes_a_link_on_the_second_line_of_a_wrapped_span(self):
        assert count_markdown_links("See `code with\n[text](note.md)` end.") == 0

    def test_count_excludes_a_link_on_the_first_line_of_a_wrapped_span(self):
        assert count_markdown_links("See `[text](note.md) code\nmore` end.") == 0

    def test_count_excludes_a_link_inside_a_crlf_wrapped_span(self):
        assert count_markdown_links("See `code with\r\n[text](note.md)` end.") == 0
        assert count_markdown_links("See `[text](note.md) code\r\nmore` end.") == 0

    def test_count_keeps_the_links_around_a_wrapped_span(self):
        text = "[b](before.md) See `code with\n[h](hidden.md)` end. [a](after.md)"
        assert count_markdown_links(text) == 2

    def test_count_keeps_a_link_between_two_wrapped_spans(self):
        text = "`a\n[h](one.md)` [v](between.md) `[h](two.md)\nb`"
        assert count_markdown_links(text) == 1

    def test_count_keeps_a_link_when_a_blank_line_ends_the_span(self):
        text = "See `a\nb` and `c\n\n[v](visible.md) d`"
        assert count_markdown_links(text) == 1


class TestDefaultIsUnchanged:
    def test_markdown_links_are_ignored_by_default(self, tmp_path):
        _write(tmp_path, "a.md", "[one](b.md)\n")
        _write(tmp_path, "b.md")
        graph = _build(tmp_path)
        assert graph.out_links["a.md"] == set()
        assert sum(graph.link_counts.values()) == 0

    def test_wikilinks_still_work_in_markdown_mode_only_if_asked(self, tmp_path):
        _write(tmp_path, "a.md", "[[b]]\n")
        _write(tmp_path, "b.md")
        assert _build(tmp_path, link_syntax="markdown").out_links["a.md"] == set()
        assert _build(tmp_path, link_syntax="both").out_links["a.md"] == {"b.md"}


class TestRelativeResolution:
    def test_a_sibling_target_resolves(self, tmp_path):
        _write(tmp_path, "docs/a.md", "[one](b.md)\n")
        _write(tmp_path, "docs/b.md")
        assert _build(tmp_path, link_syntax="markdown").out_links["docs/a.md"] == {"docs/b.md"}

    def test_a_parent_relative_target_resolves(self, tmp_path):
        _write(tmp_path, "docs/deep/a.md", "[one](../other/b.md)\n")
        _write(tmp_path, "docs/other/b.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["docs/deep/a.md"] == {"docs/other/b.md"}

    def test_an_explicit_dot_slash_resolves(self, tmp_path):
        _write(tmp_path, "docs/a.md", "[one](./b.md)\n")
        _write(tmp_path, "docs/b.md")
        assert _build(tmp_path, link_syntax="markdown").out_links["docs/a.md"] == {"docs/b.md"}

    def test_the_same_name_in_two_folders_does_not_collide(self, tmp_path):
        # The point of relative resolution: a bare name is NOT ambiguous here, because the
        # linking note's folder decides. Under wikilink rules this same pair is ambiguous.
        _write(tmp_path, "one/a.md", "[x](n.md)\n")
        _write(tmp_path, "one/n.md")
        _write(tmp_path, "two/n.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["one/a.md"] == {"one/n.md"}
        assert graph.link_counts["ambiguous"] == 0

    def test_a_target_escaping_the_vault_is_missing(self, tmp_path):
        _write(tmp_path, "a.md", "[out](../outside.md)\n")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.link_counts["missing"] == 1
        assert graph.out_links["a.md"] == set()

    def test_a_target_that_does_not_exist_is_missing(self, tmp_path):
        _write(tmp_path, "a.md", "[gone](nowhere.md)\n")
        assert _build(tmp_path, link_syntax="markdown").link_counts["missing"] == 1

    def test_a_self_link_is_not_an_edge(self, tmp_path):
        _write(tmp_path, "a.md", "[self](a.md)\n")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["a.md"] == set()
        assert graph.link_counts["resolved"] == 1

    def test_a_root_level_source_resolves_the_exact_sibling(self, tmp_path):
        # #270: PurePosixPath("b.md").parent is "." for a root-level source, so the join used to
        # degenerate to the slash-less "c.md" and get looked up by stem anywhere in the vault.
        _write(tmp_path, "b.md", "[x](c.md)\n")
        _write(tmp_path, "c.md")
        _write(tmp_path, "docs/c.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["b.md"] == {"c.md"}
        assert graph.link_counts["ambiguous"] == 0

    def test_a_nested_source_resolves_the_exact_sibling(self, tmp_path):
        # Same defect one level down: a one-component suffix match is still a global basename
        # search, so the path-suffix branch collides too without the exact-path rule.
        _write(tmp_path, "docs/b.md", "[x](c.md)\n")
        _write(tmp_path, "docs/c.md")
        _write(tmp_path, "x/docs/c.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["docs/b.md"] == {"docs/c.md"}
        assert graph.link_counts["ambiguous"] == 0

    def test_wikilinks_are_not_affected_by_the_exact_path_rule(self, tmp_path):
        # The exact-path rule is markdown-only: the same colliding shapes, linked with [[...]]
        # instead, must still be reported ambiguous.
        root_case = tmp_path / "root_case"
        _write(root_case, "b.md", "[[c]]\n")
        _write(root_case, "c.md")
        _write(root_case, "docs/c.md")
        graph = _build(root_case, link_syntax="wikilink")
        assert graph.link_counts["ambiguous"] == 1
        assert graph.out_links["b.md"] == set()

        nested_case = tmp_path / "nested_case"
        _write(nested_case, "docs/b.md", "[[docs/c]]\n")
        _write(nested_case, "docs/c.md")
        _write(nested_case, "x/docs/c.md")
        graph = _build(nested_case, link_syntax="wikilink")
        assert graph.link_counts["ambiguous"] == 1
        assert graph.out_links["docs/b.md"] == set()

    def test_autolinks_bare_targets_are_not_affected_by_the_exact_path_rule(self, tmp_path):
        # The autolinks passthrough is name-based by design; a bare target must not gain the
        # relative-rule's exact-path resolution.
        _write(tmp_path, "b.md", "[x](c.md)\n")
        _write(tmp_path, "c.md")
        _write(tmp_path, "docs/c.md")
        graph = _build(tmp_path, link_syntax="markdown-autolinks")
        assert graph.link_counts["ambiguous"] == 1
        assert graph.out_links["b.md"] == set()

    def test_diagnose_never_applies_the_exact_path_rule(self, tmp_path):
        # The public diagnose() has no source note to be relative to, so it must keep reporting
        # this collision exactly as before, regardless of what build() did with exact_paths.
        _write(tmp_path, "b.md", "[x](c.md)\n")
        _write(tmp_path, "c.md")
        _write(tmp_path, "docs/c.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert diagnose(graph, "c.md").reason == "ambiguous"


class TestRootRelativeResolution:
    # #205: pathlib's `/` operator discards the left-hand side entirely when the right-hand
    # operand is absolute, so a leading-slash target used to have the linking note's folder
    # silently dropped and could never match any catalog entry.

    def test_a_root_relative_target_resolves_to_an_existing_note(self, tmp_path):
        _write(tmp_path, "blog/post.md", "[x](/notes/foo.md)\n")
        _write(tmp_path, "notes/foo.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["blog/post.md"] == {"notes/foo.md"}
        assert graph.link_counts["missing"] == 0

    def test_a_root_relative_target_to_a_missing_note_stays_missing(self, tmp_path):
        # The basename "gone.md" exists elsewhere in the vault, so a basename-fallback regression
        # (resolving via name anywhere in the tree instead of strictly at the root-relative path)
        # would turn this green for the wrong reason.
        _write(tmp_path, "blog/post.md", "[x](/notes/gone.md)\n")
        _write(tmp_path, "other/gone.md")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.out_links["blog/post.md"] == set()
        assert graph.link_counts["missing"] == 1

    def test_root_relative_resolution_is_the_same_from_the_vault_root_and_nested(self, tmp_path):
        root_case = tmp_path / "root_case"
        _write(root_case, "a.md", "[x](/notes/foo.md)\n")
        _write(root_case, "notes/foo.md")
        root_graph = _build(root_case, link_syntax="markdown")

        nested_case = tmp_path / "nested_case"
        _write(nested_case, "x/y/z/a.md", "[x](/notes/foo.md)\n")
        _write(nested_case, "notes/foo.md")
        nested_graph = _build(nested_case, link_syntax="markdown")

        assert root_graph.out_links["a.md"] == {"notes/foo.md"}
        assert nested_graph.out_links["x/y/z/a.md"] == {"notes/foo.md"}
        assert root_graph.link_counts["missing"] == nested_graph.link_counts["missing"] == 0

    def test_a_root_relative_target_escaping_the_vault_is_missing(self, tmp_path):
        _write(tmp_path, "a.md", "[out](/../outside.md)\n")
        graph = _build(tmp_path, link_syntax="markdown")
        assert graph.link_counts["missing"] == 1
        assert graph.out_links["a.md"] == set()


class TestBothModes:
    def test_both_syntaxes_are_counted_and_conserved(self, tmp_path):
        _write(tmp_path, "a.md", "[[b]]\n[one](b.md)\n[gone](nope.md)\n")
        _write(tmp_path, "b.md")
        graph = _build(tmp_path, link_syntax="both")
        assert sum(graph.link_counts.values()) == 3
        assert graph.link_counts["resolved"] == 2
        assert graph.link_counts["missing"] == 1
        assert graph.out_links["a.md"] == {"b.md"}

    def test_a_colliding_wikilink_stays_ambiguous_alongside_a_resolvable_markdown_link(
        self, tmp_path
    ):
        # #270's exact-path eligibility must be decided per display, not by whether markdown
        # reading is on for the build: a wikilink display sharing the build with a resolvable
        # markdown link must not pick up the markdown-only exact-path rule.
        _write(tmp_path, "a.md", "[[c]]\n")
        _write(tmp_path, "c.md")
        _write(tmp_path, "docs/c.md")
        _write(tmp_path, "other.md")
        _write(tmp_path, "b.md", "[x](other.md)\n")
        graph = _build(tmp_path, link_syntax="both")
        assert graph.link_counts["ambiguous"] == 1
        assert graph.out_links["a.md"] == set()
        assert graph.out_links["b.md"] == {"other.md"}

    def test_the_unread_syntax_warning_is_silent_once_markdown_is_read(self, tmp_path, capsys):
        _write(tmp_path, "a.md", "[1](b.md)\n[2](b.md)\n[3](b.md)\n")
        _write(tmp_path, "b.md")
        _build(tmp_path, link_syntax="both")
        assert capsys.readouterr().err == ""


class TestConfig:
    def test_an_unknown_syntax_is_rejected(self, tmp_path):
        _write(tmp_path, "a.md")
        try:
            _build(tmp_path, link_syntax="logseq")
        except ValueError as e:
            assert "link_syntax" in str(e)
        else:
            raise AssertionError("an unknown link_syntax must fail loudly")

    def test_it_loads_from_toml(self, tmp_path):
        from graphmark.config import load_config

        cfg = tmp_path / "v.toml"
        cfg.write_text(f'root = "{tmp_path}"\nlink_syntax = "both"\n', encoding="utf-8")
        assert load_config(cfg).link_syntax == "both"
