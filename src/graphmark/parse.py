"""Note parsing: document splitting and wikilink extraction."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from graphmark.model import Document

# Frontmatter delimiters tolerate CRLF (Windows / git-autocrlf vaults) and a closing `---` that
# sits at EOF with no trailing newline (a frontmatter-only note). A block that fails to split
# would stay in the body, turning frontmatter wikilinks into phantom graph edges.
_FM_RE = re.compile(r"^---\r?\n(.+?\r?\n)---(?:\r?\n|\Z)", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")


def _strip_fenced_blocks(text: str) -> str:
    """Remove fenced code block contents so wikilinks inside them are ignored.

    Tracks the opening fence's character *and* length; a line only closes the fence when it is
    the same character with length >= the opening length (CommonMark's fence-closing rule). This
    stops a shorter nested fence of the same character from closing a longer outer fence early.
    """
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    for line in lines:
        ls = line.lstrip()
        if fence_char is None:
            m = _FENCE_OPEN_RE.match(ls)
            if m:
                fence_char = ls[0]
                fence_len = len(m.group(1))
            else:
                out.append(line)
        else:
            m = _FENCE_OPEN_RE.match(ls)
            if m and ls[0] == fence_char and len(m.group(1)) >= fence_len:
                fence_char = None
                fence_len = 0
    return "".join(out)


#: A block-list item line: leading whitespace, a dash, then the value. Checked before the
#: key/value split because an item may itself contain a colon ("- Note: A Subtitle") — the dash
#: decides, not the colon.
_BLOCK_ITEM_RE = re.compile(r"^\s+-\s*(.*)$")


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
    for line in raw.splitlines():
        item = _BLOCK_ITEM_RE.match(line)
        if item is not None and current_list_key is not None:
            value = item.group(1).strip().strip("\"'")
            if value:
                # The key held "" until its first item arrived; replace it with the list.
                if not isinstance(result.get(current_list_key), list):
                    result[current_list_key] = []
                result[current_list_key].append(value)
            continue

        current_list_key = None
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [v.strip().strip("\"'") for v in value[1:-1].split(",")]
            result[key] = [i for i in items if i]
        else:
            result[key] = value.strip("\"'")
            # A bare "key:" may open a block list; the next line decides.
            if not value:
                current_list_key = key
    return result


class WikilinkExtractor:
    """Extracts raw wikilink displays from note text, excluding code spans."""

    def extract(self, text: str) -> list[str]:
        text = _strip_fenced_blocks(text)
        text = _INLINE_CODE_RE.sub("", text)
        return _WIKILINK_RE.findall(text)


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
    m = _FM_RE.match(raw)
    if m:
        frontmatter = _parse_frontmatter(m.group(1))
        body = raw[m.end() :]
    else:
        frontmatter = {}
        body = raw
    return Document(rel_path=rel_path, text=body, frontmatter=frontmatter)
