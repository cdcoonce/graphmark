"""Note parsing: document splitting and wikilink extraction."""

from __future__ import annotations

import csv
import io
import re
import sys
from pathlib import Path
from urllib.parse import unquote

from graphmark.model import Document

# Frontmatter delimiters tolerate CRLF (Windows / git-autocrlf vaults) and a closing `---` that
# sits at EOF with no trailing newline (a frontmatter-only note). A block that fails to split
# would stay in the body, turning frontmatter wikilinks into phantom graph edges. Trailing ASCII
# space/tab after either `---` (a paste or auto-format artifact) is tolerated for the same reason.
# The whole capture group is optional so two adjacent `---` lines (an empty block) still split;
# group(1) is then None, which the call site maps to "".
_FM_RE = re.compile(r"^---[ \t]*\r?\n(.*?\r?\n)??---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")


def _strip_fenced_blocks(text: str) -> tuple[str, bool]:
    """Remove fenced code block contents so wikilinks inside them are ignored.

    Tracks the opening fence's character *and* length; a line only closes the fence when it is
    the same character with length >= the opening length, followed by nothing but optional
    trailing whitespace (CommonMark's fence-closing rule). This stops a shorter nested fence of
    the same character from closing a longer outer fence early, and stops a same-length-or-longer
    fence run that carries trailing content (e.g. an info string like ```python``) from being
    mistaken for a closer.

    CommonMark only recognizes a fence delimiter -- open or close -- when its leading whitespace
    is 0-3 characters; 4+ leading characters makes it an indented code block, and any
    backticks/tildes on it are literal text, not a fence. This is checked on both the open and
    the close side, measured from the start of the physical line (no container/list/blockquote
    budget). Indentation is counted in raw characters: a tab counts as one character, not
    expanded to CommonMark's 4-column tab stop -- a documented simplification, not full
    CommonMark tab fidelity.

    Returns ``(stripped_text, unterminated)``, where ``unterminated`` is ``True`` iff a fence was
    still open when the text ended (an unclosed ``` `` `` or ``~~~`` that silently drops every
    line after it, including any links). The caller decides what, if anything, to do with that
    flag -- this function has no file identity to put in a diagnostic.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    for line in lines:
        ls = line.lstrip()
        indent = len(line) - len(ls)
        if fence_char is None:
            m = _FENCE_OPEN_RE.match(ls)
            if m and indent <= 3:
                fence_char = ls[0]
                fence_len = len(m.group(1))
            else:
                out.append(line)
        else:
            m = _FENCE_OPEN_RE.match(ls)
            if (
                m
                and indent <= 3
                and ls[0] == fence_char
                and len(m.group(1)) >= fence_len
                and ls[m.end() :].strip() == ""
            ):
                fence_char = None
                fence_len = 0
    return "".join(out), fence_char is not None


def _strip_non_link_regions(text: str) -> str:
    """Strip fenced blocks and inline code spans -- the text that is never eligible to hold a link.

    Both `count_markdown_links` and the two `LinkExtractor` implementations need to answer the same
    question before they can extract anything: what text is left once code is excluded? This is
    that shared answer, kept in one place so the three callers cannot silently drift out of
    lock-step on what counts as code. The `_strip_fenced_blocks` `unterminated` flag is discarded
    here, exactly as every caller already discarded it before this helper existed.
    """
    text, _ = _strip_fenced_blocks(text)
    return _INLINE_CODE_RE.sub("", text)


#: A block-list item line: leading whitespace, a dash, then the value. Checked before the
#: key/value split because an item may itself contain a colon ("- Note: A Subtitle") — the dash
#: decides, not the colon.
_BLOCK_ITEM_RE = re.compile(r"^\s*-\s*(.*)$")


def _strip_paired_quotes(value: str) -> str:
    """Unwrap one surrounding quote pair, only when both ends carry the SAME quote character.

    A blanket ``str.strip("\"'")`` removes any run of quote characters from either end whether or
    not they pair up, so an unquoted ``Believin'`` lost its apostrophe. A value that is not
    wrapped in a matching pair (including a lone quote character) is returned unchanged.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_frontmatter(raw: str) -> dict:
    """Minimal YAML-like frontmatter parser: scalar, quoted-string, inline-list, block-list.

    Deliberately a targeted scan rather than a YAML dependency — this runs over every note in a
    vault, and a note someone is mid-edit must not take the graph down. Anything unparseable
    yields nothing rather than raising.

    Block lists (``key:`` followed by indented ``- item`` lines) are what Obsidian's own
    Properties UI writes, so they are the common form in real vaults, not an edge case. They
    produce the same ``list[str]`` an inline list does. A ``key:`` with no items that follow stays
    ``""`` — an empty value, not an empty list.
    """
    result: dict = {}
    current_list_key: str | None = None
    in_nested_mapping = False
    for line in raw.splitlines():
        if not line.strip():
            # A blank line is whitespace, not structure: it neither closes an open block list nor
            # opens anything, so an item after it still belongs to the list.
            continue
        item = _BLOCK_ITEM_RE.match(line)
        if item is not None:
            # A "- item" line is never a key/value pair. With no list open it is a stray: drop it
            # rather than fall through, where a colon in its text would store a "- key" entry.
            if current_list_key is not None:
                value = _strip_paired_quotes(item.group(1).strip())
                if value:
                    # The key held "" until its first item arrived; replace it with the list.
                    if not isinstance(result.get(current_list_key), list):
                        result[current_list_key] = []
                    result[current_list_key].append(value)
            continue

        # An indented non-item line straight after a bare "key:" is a nested mapping's subkey, an
        # unsupported shape: drop it (and its siblings) rather than let the generic branch below
        # promote it to a top-level key. Gated on a block having been open BEFORE the reset, so a
        # stray line with no open block is left to the existing behavior.
        if line[:1].isspace() and line.strip():
            if current_list_key is not None or in_nested_mapping:
                in_nested_mapping = True
                current_list_key = None
                continue
        elif line.strip():
            in_nested_mapping = False

        current_list_key = None
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            if not inner:
                # csv.reader over an empty string raises StopIteration on next(); an empty
                # bracket ("key: []") is a valid empty list, not unparseable input.
                items = []
            else:
                row = next(csv.reader(io.StringIO(inner), skipinitialspace=True))
                items = [_strip_paired_quotes(v.strip()) for v in row]
            result[key] = [i for i in items if i]
        elif value.startswith("["):
            # A flow list that does not close on this line (wrapped across lines, or never
            # closed) is unparseable: drop the key rather than store a truncated literal.
            pass
        else:
            result[key] = _strip_paired_quotes(value)
            # A bare "key:" may open a block list; the next line decides.
            if not value:
                current_list_key = key
    return result


#: A markdown-style link to a local markdown file: ``[text](note.md)``,
#: ``[text](../a/b.md#Anchor)``, a titled link (``[text](note.md "A Title")``), an
#: angle-bracket-escaped target (``[text](<my note.md>)``, the standard escape for a path
#: containing spaces/parens), or the two combined. The single capture group holds the raw target,
#: angle brackets included when present — see ``_strip_angle_brackets``, its consumers' shared
#: unwrap step.
#: Not an image (``![...]``) and not an absolute URL — a link to somebody's README on the web is not
#: a link into this vault. Deliberately narrow: this counts a *signal*, so a false positive here
#: would produce a warning about nothing.
_MD_LINK_RE = re.compile(
    r'(?<!!)\[[^\]]*\]\((?!\w+:)(<[^<>]+?\.md>|[^)\s<>]+?\.md)(?:#[^)"]*?)?(?:\s+"[^"]*")?\)',
    re.IGNORECASE,
)


def _strip_angle_brackets(target: str) -> str:
    """Unwrap a `<...>`-escaped markdown target, leaving a bare target untouched.

    Both `_MD_LINK_RE` consumers that care about the target's text (not just its count) need this
    same unwrap, so it lives here once rather than twice.
    """
    if target.startswith("<") and target.endswith(">"):
        return target[1:-1]
    return target


def count_markdown_links(text: str) -> int:
    """How many ``[text](note.md)`` links the text holds — a syntax graphmark does not read.

    graphmark extracts ``[[wikilinks]]`` only, so a vault written in markdown link syntax produces
    an empty graph with no indication that anything was missed: every note an orphan, no clusters,
    and a `check` that looks healthy because links which were never extracted are not *unresolved*.

    The conservation law in ``VaultGraph.build`` cannot see this — it sums over what the extractor
    produced, so a syntax the extractor does not know sits outside the universe being counted. This
    function exists to make that universe's edge visible; it feeds a warning and nothing else.

    Code spans and fenced blocks are skipped, exactly as wikilink extraction skips them: a
    documented example is not a link.
    """
    text = _strip_non_link_regions(text)
    return len(_MD_LINK_RE.findall(text))


class WikilinkExtractor:
    """Extracts raw wikilink displays from note text, excluding code spans."""

    def extract(self, text: str) -> list[str]:
        text = _strip_non_link_regions(text)
        return _WIKILINK_RE.findall(text)


class MarkdownLinkExtractor:
    """Extracts ``[text](note.md)`` targets — the syntax non-Obsidian markdown vaults use.

    Returns the **target**, not the display text, and without its anchor: unlike a wikilink, where
    the visible text names the note, here the parenthesized path is the only thing that identifies
    it. The display text is prose and never resolves to anything.

    Percent-encoding is decoded, because markdown encodes spaces (``my%20note.md``) while the vault
    stores them literally — a link no editor would consider broken.

    The returned target is **relative to the linking note**, which callers must resolve; this class
    cannot, since ``extract`` sees text and never learns which note it came from. See
    ``VaultGraph.build``.
    """

    def extract(self, text: str) -> list[str]:
        text = _strip_non_link_regions(text)
        return [unquote(_strip_angle_brackets(target)) for target in _MD_LINK_RE.findall(text)]


def parse_document(path: Path, root: Path) -> Document:
    """Parse a markdown note into a Document, splitting YAML frontmatter from body.

    A note that is not valid UTF-8 is decoded with ``errors="replace"`` so it stays in the
    graph (undecodable spans are lost) rather than crashing the whole build; exactly one
    warning line per affected file goes to stderr, never stdout.
    """
    rel_path = path.relative_to(root).as_posix()
    data = path.read_bytes()
    try:
        raw = data.decode("utf-8")
    except UnicodeDecodeError:
        raw = data.decode("utf-8", errors="replace")
        print(
            f"graphmark: warning: {rel_path}: invalid UTF-8, decoded with replacement",
            file=sys.stderr,
        )
    # A UTF-8 BOM sits ahead of the `---` and defeats _FM_RE's anchored match, so a BOM'd note
    # would have no frontmatter at all: its aliases would never register (a phantom break) and its
    # frontmatter wikilinks would stay in the body (a phantom edge — the very failure the regex
    # above exists to prevent). Stripped here, on the decoded text, so the frontmatter split, the
    # body and the extractor all see the same string on both decode paths. Leading only: elsewhere
    # U+FEFF is a zero-width no-break space, which is legitimate content. lstrip rather than a
    # single removal because double-encoding produces doubled BOMs, and one survivor still breaks
    # the match.
    raw = raw.lstrip("﻿")
    m = _FM_RE.match(raw)
    if m:
        frontmatter = _parse_frontmatter(m.group(1) or "")
        body = raw[m.end() :]
    else:
        frontmatter = {}
        body = raw
    # Checked here, once, so the warning fires exactly one time per affected file regardless of
    # how many extractors (WikilinkExtractor, MarkdownLinkExtractor, count_markdown_links) later
    # call _strip_fenced_blocks on this same body during a build -- see that function's docstring.
    _, unterminated = _strip_fenced_blocks(body)
    if unterminated:
        print(
            f"graphmark: warning: {rel_path}: unterminated fenced code block, "
            "trailing content dropped",
            file=sys.stderr,
        )
    return Document(rel_path=rel_path, text=body, frontmatter=frontmatter)
