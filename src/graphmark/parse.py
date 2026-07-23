"""Note parsing: document splitting and wikilink extraction."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from graphmark.model import Document

_FM_RE = re.compile(r"^---\n(.+?\n)---\n", re.DOTALL)
_WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")


def _strip_fenced_blocks(text: str) -> str:
    """Remove fenced code block contents so wikilinks inside them are ignored."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    fence_char: str | None = None
    for line in lines:
        ls = line.lstrip()
        if fence_char is None:
            m = _FENCE_OPEN_RE.match(ls)
            if m:
                fence_char = ls[0]
            else:
                out.append(line)
        else:
            if _FENCE_OPEN_RE.match(ls) and ls[0] == fence_char:
                fence_char = None
    return "".join(out)


def _parse_frontmatter(raw: str) -> dict:
    """Minimal YAML-like frontmatter parser covering scalar, quoted-string, inline-list."""
    result: dict = {}
    for line in raw.splitlines():
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
    return result


class WikilinkExtractor:
    """Extracts raw wikilink displays from note text, excluding code spans."""

    def extract(self, text: str) -> list[str]:
        text = _strip_fenced_blocks(text)
        text = _INLINE_CODE_RE.sub("", text)
        return _WIKILINK_RE.findall(text)


def parse_document(path: Path, root: Path) -> Document:
    """Parse a markdown note into a Document, splitting YAML frontmatter from body."""
    rel_path = path.relative_to(root).as_posix()
    raw_bytes = path.read_bytes()
    try:
        raw = raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw = raw_bytes.decode("utf-8", errors="replace")
        print(
            f"graphmark: warning: {rel_path}: invalid UTF-8, decoded with replacement",
            file=sys.stderr,
        )
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    m = _FM_RE.match(raw)
    if m:
        frontmatter = _parse_frontmatter(m.group(1))
        body = raw[m.end() :]
    else:
        frontmatter = {}
        body = raw
    return Document(rel_path=rel_path, text=body, frontmatter=frontmatter)
